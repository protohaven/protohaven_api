"""Helpers for updating clearance codes attached to users in Neon"""

import logging
from functools import lru_cache

from protohaven_api.integrations import airtable, mqtt, neon

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
    delta = set(delta)
    name_to_code, code_to_id = code_mapping()
    m = list(neon.search_member(email))
    if len(m) == 0:
        raise KeyError(f"Member {email} not found")
    m = m[0]
    if m.neon_id == m.company_id:
        raise TypeError(f"Account with email {email} is a company; expected individual")
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
        log.info(f"No change required for {email}; skipping {method}")
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
