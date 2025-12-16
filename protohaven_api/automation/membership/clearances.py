"""Helpers for updating clearance codes attached to users in Neon"""

import datetime
import logging
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache

from dateutil import parser as dateparser

from protohaven_api.config import tz, tznow
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


type Email = str
type ToolCode = str
type NeonID = str
type Hours = float
type TimeInterval = tuple[datetime.datetime, datetime.datetime]

RECERT_EPOCH = dateparser.parse("2024-01-01").astimezone(tz)


def compute_recert_deadlines(
    cfg: airtable.RecertConfig,
    last_earned: datetime.datetime | None,
    last_passing_quiz: datetime.datetime | None,
    related_reservation_hours: dict[datetime.datetime, Hours],
) -> tuple[datetime.datetime | None, datetime.datetime | None]:
    """Return deadline for when the clearance with this data is due for recertification.

    Both the "instruction" deadline (which would undo an expired recert) and the
    "reservation based" deadline (which would not undo an expired recert) are returned.

    If last_earned is missing, we assume a default "epoch" date.

    If no reservations, then the reservation deadline matches the instructor deadline

    PRECONDITION: The member we are computing deadlines for has already earned the
    clearance. We assume missing "last_earned" info to mean the information is missing,
    and assume that they were cleared at some point in the past.
    """

    # If clearance doesn't expire, no deadline
    if not cfg.expiration:
        return None, None

    last_earned = last_earned or RECERT_EPOCH
    last_passing_quiz = last_passing_quiz or RECERT_EPOCH
    inst_deadline = max(last_earned, last_passing_quiz) + cfg.expiration

    acc_hours = 0.0
    res_deadline = inst_deadline  # default to instructor deadline
    for ts, hours in sorted(
        list(related_reservation_hours.items()), key=lambda v: v[0], reverse=True
    ):
        acc_hours += hours
        if acc_hours < cfg.bypass_hours:
            continue
        # Latest possible candidate for deadline based on reservation hours
        res_deadline = ts + cfg.bypass_cutoff
        break

    # Otherwise it's just the expiration date. Truncate non-date info for
    # easier comparison to what's in Airtable
    inst_deadline = inst_deadline.replace(hour=0, minute=0, second=0, microsecond=0)
    res_deadline = res_deadline.replace(hour=0, minute=0, second=0, microsecond=0)
    return inst_deadline, res_deadline


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
            log.debug(
                "Could not resolve reservation resource ID "
                f"{res['resourceId']} to tool code; ignoring"
            )
            continue
        neon_id = email_to_neon_id.get(booked_user_map.get(res["userId"]))
        if not neon_id:
            log.debug(
                f"Could not resolve booked user ID {res['userId']} to Neon ID; ignoring"
            )
            continue
        result[(neon_id, tool_code)].append((res["startDate"], res["endDate"]))
    return result


@dataclass
class RecertEnv:
    """All of the data needed to evaluate recertification for all members"""

    recert_configs: dict[ToolCode, airtable.RecertConfig]
    pending: dict[tuple[NeonID, ToolCode], airtable.PendingRecert]
    neon_clearances: dict[NeonID, set[ToolCode]]
    last_earned: dict[tuple[NeonID, ToolCode], datetime.datetime]
    last_passing_quiz: dict[tuple[NeonID, ToolCode], datetime.datetime]
    reservations: dict[tuple[NeonID, ToolCode], list[TimeInterval]]
    contact_info: dict[NeonID, tuple[str, Email]]


def build_recert_env(  # pylint: disable=too-many-locals
    from_date: datetime.datetime, from_row=1300
) -> RecertEnv:
    """Examine Neon CRM, instructor logs, and recert quizzes to identify which
    members are due for recertification"""

    # Execute fetches in parallel and process early where possible to reduce load time
    with ThreadPoolExecutor() as executor:
        log.info("Async fetching tool recertification configs from Airtable")
        recert_configs_future = executor.submit(
            airtable.get_tool_recert_configs_by_code
        )

        log.info("Async fetching all members' clearances from neon")
        # Note: this only asyncs the first fetch; would be better to
        # resubmit to the executor like in events.py, but
        # honestly it's probably going to be the longest part of the fetches anyways
        neon_clearances_future = executor.submit(
            neon.search_all_members,
            fields=[
                neon.CustomField.CLEARANCES,
                "First Name",
                "Email 1",
                "Email 2",
                "Email 3",
            ],
            fetch_memberships=False,
            also_fetch=False,
        )

        log.info("Async fetching pending recerts table from Airtable")
        pending_future = executor.submit(airtable.get_pending_recertifications)

        log.info("Async fetching all quiz results")
        quiz_results_future = executor.submit(
            airtable.get_latest_passing_quizzes_by_email_and_tool
        )

        log.info(f"Async fetching all instructor logged clearances past row {from_row}")
        instructor_clearances_future = executor.submit(
            sheets.get_passing_student_clearances, from_row=from_row
        )

        neon_clearances: dict[str, set[str]] = {}
        email_to_neon_id = {}
        contact_info = {}

        log.info("Handling neon clearance results")
        for mem in neon_clearances_future.result():
            sys.stderr.write(".")
            sys.stderr.flush()
            clr = {c.split(":")[0].strip() for c in mem.clearances}
            if clr:
                neon_clearances[mem.neon_id] = clr
            for e in mem.all_emails():
                if e:
                    email_to_neon_id[e] = mem.neon_id
            contact_info[mem.neon_id] = (mem.fname, mem.email)
        log.info("Email map built")

        log.info(f"Async fetching hours of tool reservations from {from_date}")
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
                log.debug(f"Failed to resolve email {email} to a Neon ID, ignoring")
                continue
            for code in resolve_codes(clearance_codes or []) + (tool_codes or []):
                cur = last_earned.get((nid, code))
                if not cur or timestamp > cur:
                    last_earned[(nid, code)] = timestamp

        # Convert airtable quiz results from email key to neon ID key
        last_passing_quiz: dict[tuple[NeonID, ToolCode], datetime.datetime] = {}
        for k, d in quiz_results_future.result().items():
            email, code = k
            nid = email_to_neon_id.get(email.strip().lower())
            if not nid:
                log.debug(f"Failed to resolve email {email} to a Neon ID, ignoring")
                continue
            last_passing_quiz[(nid, code)] = d

        recert_configs = recert_configs_future.result()
        reservations = reservations_future.result()

        pending = {}
        for p in pending_future.result():
            pending[(p.neon_id, p.tool_code)] = p

    return RecertEnv(
        recert_configs,
        pending,
        neon_clearances,
        last_earned,
        last_passing_quiz,
        reservations,
        contact_info,
    )


type RecertsDict = dict[
    tuple[NeonID, ToolCode], tuple[datetime.datetime, datetime.datetime]
]


def segment_by_recertification_needed(  # pylint: disable=too-many-locals
    env: RecertEnv, now: datetime.datetime
) -> tuple[RecertsDict, RecertsDict]:
    """Given all relevant information, compute the set of member-clearances needing
    recertification and those that do not need recertification."""
    log.info("Searching for member clearances that are due for recertification")
    needed: RecertsDict = {}
    not_needed: RecertsDict = {}

    # Note: ground truth are the clearances the user has in Neon.
    # However, there's a point where a clearance has been suspended due to
    # expiration of certification, but we still need to track it.
    neon_ids = set(env.neon_clearances.keys()).union(
        set(n for n, _ in env.pending.keys())
    )

    for neon_id in neon_ids:
        # Given the combo of sets above, we are *only* iterating over members who received
        # these clearances in the past. Taking a quiz without getting instruction should not
        # count as being cleared.
        cc = set(env.neon_clearances.get(neon_id) or [])
        pending_cc = {c for n, c in env.pending.keys() if str(n) == str(neon_id)}

        for tool_code in cc.union(pending_cc):
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

            inst_deadline, res_deadline = compute_recert_deadlines(
                cfg,
                env.last_earned.get((neon_id, tool_code)),
                env.last_passing_quiz.get((neon_id, tool_code)),
                related_reservation_hours,
            )
            if inst_deadline and now >= inst_deadline and not res_deadline:
                needed[(neon_id, tool_code)] = (inst_deadline, res_deadline)
            elif (
                inst_deadline
                and now >= inst_deadline
                and res_deadline
                and now >= res_deadline
            ):
                needed[(neon_id, tool_code)] = (inst_deadline, res_deadline)
            else:
                not_needed[(neon_id, tool_code)] = (inst_deadline, res_deadline)

    assert not set(needed.keys()).intersection(set(not_needed.keys()))
    return needed, not_needed
