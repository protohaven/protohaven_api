"""Helpers for updating clearance codes attached to users in Neon"""

import datetime
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache

from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, booked, mqtt, neon, neon_base, sheets

log = logging.getLogger("handlers.admin")


@lru_cache(maxsize=1)
def code_mapping():
    """Fetch neon's current mapping of clearance -> tool code and tool code -> id"""
    all_codes = neon.fetch_clearance_codes()
    name_to_code = {c["name"]: c["code"] for c in all_codes}
    code_to_id = {c["code"]: c["id"] for c in all_codes}
    return name_to_code, code_to_id


def update(email, method, delta, apply=True):
    """Update clearances for `email` user"""
    m = list(neon.search_members_by_email(email))
    if len(m) == 0:
        raise KeyError(f"Member {email} not found")
    return update_by_member(m[0], method, delta, apply)


def update_by_neon_id(neon_id, method, delta, apply=True):
    """Update clearances for `email` user"""
    m = neon_base.fetch_account(neon_id, required=True)
    return update_by_member(m, method, delta, apply)


def update_by_member(m, method, delta, apply=True):
    """Update clearances for `email` user"""
    delta = set(delta)
    name_to_code, code_to_id = code_mapping()
    if m.neon_id == m.company_id:
        raise TypeError(
            f"Account with email {m.email} is a company; expected individual"
        )
    codes = {name_to_code.get(n) for n in m.clearances if n != ""}
    initial_codes = set(codes)
    result = set()
    if method == "GET":
        return [c for c in codes if c is not None]
    if method == "PATCH":
        result = delta - codes
        codes.update(delta)
    elif method == "DELETE":
        result = codes - delta
        codes -= set(delta)

    if codes == initial_codes:
        log.info(f"No change required for {m.email}; skipping {method}")
        return []

    ids = {code_to_id[c] for c in codes if c in code_to_id.keys()}
    if apply:
        log.info(f"Setting clearances for {m.neon_id} to {ids}")
        content = neon.set_clearances(m.neon_id, ids, is_company=False)
        log.info("Neon response: %s", str(content))
        for d in delta:
            mqtt.notify_clearance(m.neon_id, d, added=method == "PATCH")
    return list(result)


def resolve_codes(initial: list):
    """Resolve clearance groups (e.g. MWB) into multiple tools (ABG, RBP...)"""
    mapping = airtable.get_clearance_to_tool_map()  # cached
    delta = []
    for c in initial:
        if c in mapping:
            delta += list(mapping[c])
        else:
            delta.append(c)
    return delta


Email = str
ToolCode = str
NeonID = int
Hours = float
TimeInterval = tuple[datetime.datetime, datetime.datetime]


def is_recert_due(
    cfg: airtable.RecertConfig,
    now: datetime.datetime,
    last_earned: datetime.datetime,
    related_reservation_hours: dict[datetime.datetime, Hours],
):
    """Return true if the clearance with this data is due for recertification"""

    # If clearance doesn't expire, not due
    if not cfg.expiration:
        return False

    # If clearance isn't expired yet, not due
    if last_earned + cfg.expiration > now:
        log.debug("Recert not due; clearance not yet expired")
        return False

    # If reservations indicate sustained usage, not due
    cutoff = now - cfg.bypass_cutoff
    total_tool_time = sum(
        hours for ts, hours in related_reservation_hours.items() if ts > cutoff
    )
    if total_tool_time >= cfg.bypass_hours:
        log.debug(
            f"Recert not due; tool time {total_tool_time} > "
            f"bypass hours {cfg.bypass_hours} since {cutoff}"
        )
        return False

    return True


def _structured_reservations(
    from_date: datetime.datetime,
    to_date: datetime.datetime,
    email_to_neon_id: dict[Email, NeonID],
) -> dict[tuple[NeonID, ToolCode], list[TimeInterval]]:
    res_id_to_tool_code: dict[booked.ResourceID, ToolCode] = {
        v: k for k, v in booked.get_resource_map().items()
    }
    result = defaultdict(list)
    booked_user_map: dict[int, Email] = {
        int(u["id"]): u["emailAddress"] for u in booked.get_all_users()
    }
    for res in booked.get_reservations(from_date, to_date)["reservations"]:
        tool_code = res_id_to_tool_code.get(res["resourceId"])
        if not tool_code:
            log.warning(
                "Could not resolve reservation resource ID "
                f"{res['resourceId']} to tool code; ignoring"
            )
            continue
        neon_id = email_to_neon_id.get(booked_user_map.get(res["userId"]))
        if not neon_id:
            log.warning(
                f"Could not resolve booked user ID {res['userId']} to Neon ID; ignoring"
            )
            continue
        result[(neon_id, tool_code)].append((res["startDate"], res["endDate"]))
    return result


@dataclass
class RecertEnv:
    """All of the data needed to evaluate recertification for all members"""

    recert_configs: dict[ToolCode, airtable.RecertConfig]
    neon_clearances: dict[NeonID, set[ToolCode]]
    last_earned: dict[tuple[NeonID, ToolCode], datetime.datetime]
    reservations: dict[tuple[NeonID, ToolCode], list[TimeInterval]]


def build_recert_env(  # pylint: disable=too-many-locals
    from_date: datetime.datetime, from_row=1300
) -> RecertEnv:
    """Examine Neon CRM, instructor logs, and recert quizzes to identify which
    members are due for recertification"""

    # Execute fetches in parallel and process early where possible to reduce load time
    with ThreadPoolExecutor() as executor:
        log.info("Fetching tool recertification configs from Airtable")
        recert_configs_future = executor.submit(
            airtable.get_tool_recert_configs_by_code
        )

        log.info("Fetching all members' clearances from neon")
        neon_clearances_future = executor.submit(
            neon.search_all_members, fields=[neon.CustomField.CLEARANCES]
        )

        log.info(f"Fetching all instructor logged clearances past row {from_row}")
        instructor_clearances_future = executor.submit(
            sheets.get_passing_student_clearances, from_row=from_row
        )

        neon_clearances = {}
        email_to_neon_id = {}
        for mem in neon_clearances_future.result():
            neon_clearances[mem.neon_id] = mem.clearances
            for e in mem.emails:
                email_to_neon_id[e] = mem.neon_id
        log.info("Email map built")

        log.info(f"Fetching hours of tool reservations from {from_date}")
        reservations_future = executor.submit(
            _structured_reservations, from_date, tznow(), email_to_neon_id
        )

        instructor_clearances = instructor_clearances_future.result()
        last_earned: dict[tuple[NeonID, ToolCode], datetime.datetime] = {}
        for (
            email,
            clearance_codes,
            tool_codes,
            timestamp,
        ) in instructor_clearances:
            nid = email_to_neon_id.get(email)
            if not nid:
                log.warning(f"Failed to resolve email {email} to a Neon ID, ignoring")
            for code in resolve_codes(clearance_codes or []) + tool_codes:
                cur = last_earned.get((nid, code))
                if not cur or timestamp > cur:
                    last_earned[(nid, code)] = timestamp

        recert_configs = recert_configs_future.result()
        reservations = reservations_future.result()

    return RecertEnv(recert_configs, neon_clearances, last_earned, reservations)


def segment_by_recertification_needed(
    env: RecertEnv, deadline: datetime.datetime
) -> tuple[set[tuple[NeonID, ToolCode]], set[tuple[NeonID, ToolCode]]]:
    """Given all relevant information, compute the set of member-clearances needing
    recertification and those that do not need recertification."""
    log.info("Searching for member clearances that are due for recertification")
    needed = set()
    not_needed = set()
    for neon_id, cc in env.neon_clearances.items():
        for tool_code in cc:
            cfg = env.recert_configs.get(tool_code)
            if not cfg:
                continue

            # Construct related reservation times based on tools
            # which count for bypassing recert requirements.
            # Only count one of potentially several tools reserved
            # at the same time.
            # Note that this has the potential to overcount hours
            # If reservations are made with slight offsets
            # We can potentially reuse some stuff from scheduler.py to
            # improve this.
            related_reservation_hours: dict[datetime.datetime, Hours] = {}
            for bypass_tool in cfg.bypass_tools:
                for start, end in env.reservations.get((neon_id, bypass_tool)) or []:
                    cur = related_reservation_hours.get(start)
                    hours = (end - start).total_seconds() / 3600
                    if not cur or hours > cur:
                        related_reservation_hours[start] = hours

            if is_recert_due(
                cfg,
                deadline,
                env.last_earned[(neon_id, tool_code)],
                related_reservation_hours,
            ):
                needed.add((neon_id, tool_code))
            else:
                not_needed.add((neon_id, tool_code))

    assert not needed.intersection(not_needed)
    return needed, not_needed
