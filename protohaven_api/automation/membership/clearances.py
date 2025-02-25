"""Helpers for updating clearance codes attached to users in Neon"""

import logging
from functools import lru_cache

from protohaven_api.integrations import airtable, comms, mqtt, neon, tasks

log = logging.getLogger("handlers.admin")


@lru_cache(maxsize=1)
def code_mapping():
    all_codes = neon.fetch_clearance_codes()
    name_to_code = {c["name"]: c["code"] for c in all_codes}
    code_to_id = {c["code"]: c["id"] for c in all_codes}
    return name_to_code, code_to_id


def update(email, method, delta):
    name_to_code, code_to_id = code_mapping()
    m = list(neon.search_member(email))
    if len(m) == 0:
        return "NotFound"
    m = m[0]
    if m["Account ID"] == m["Company ID"]:
        raise FailedPrecondition(
            f"Account with email {email} is a company; expected individual"
        )
    codes = {
        name_to_code.get(n) for n in (m.get("Clearances") or "").split("|") if n != ""
    }
    if method == "GET":
        return [c for c in codes if c is not None]
    if method == "PATCH":
        codes.update(delta)
    elif method == "DELETE":
        codes -= set(delta)

    ids = {code_to_id[c] for c in codes if c in code_to_id.keys()}
    log.info(f"Setting clearances for {m['Account ID']} to {ids}")
    content = neon.set_clearances(m["Account ID"], ids, is_company=False)
    log.info("Neon response: %s", str(content))
    for d in delta:
        mqtt.notify_clearance(m["Account ID"], d, added=method == "PATCH")
    return "OK"


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
