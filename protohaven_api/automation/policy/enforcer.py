"""Policy enforcement methods for ensuring proper handling of
storage, equipment damage, and other violations"""

import datetime
import logging
from collections import defaultdict

from protohaven_api.config import safe_parse_datetime, tz, tznow
from protohaven_api.integrations import airtable, neon_base
from protohaven_api.integrations.comms import Msg

VIOLATION_MAX_AGE_DAYS = 90
OPEN_VIOLATION_GRACE_PD_DAYS = 14


log = logging.getLogger("policy_enforcement.enforcer")


def enforcement_summary(violations, fees, target):
    """Generate a summary of violation state, if any"""
    # Make sure we're only looking at open/unresolved policy stuff
    violations = [v for v in violations if not v["fields"].get("Closure")]
    fees = [f for f in fees if not f["fields"].get("Paid")]

    # Condense violation and fee info into a list of updates
    vs = {}
    for v in violations:
        vs[v["id"]] = {
            "onset": safe_parse_datetime(v["fields"]["Onset"]),
            "fee": v["fields"].get("Daily Fee", 0),
            "suspect": "known" if v["fields"].get("Neon ID") else "unknown",
            "notes": v["fields"].get("Notes", ""),
            "unpaid": 0,
        }
    for f in fees:
        amt = f["fields"]["Amount"]
        if f["fields"].get("Paid"):
            continue
        vid = f["fields"].get("Violation", [None])[0]
        if vs.get(vid):
            vs[vid]["unpaid"] += amt

    if len(vs) > 0:
        return Msg.tmpl(
            "enforcement_summary",
            vs=vs.values(),
            target=target,
        )
    return None


def gen_fees(violations=None, latest_fee=None, now=None):
    """Create a list of all additional fees due to open violations
    since the last time the fee generator was run.
    This backfills fees beyond the current day."""
    fees = []

    if violations is None:
        violations = airtable.get_policy_violations()
    if latest_fee is None:
        latest_fee = {}
        for f in airtable.get_policy_fees():
            d = safe_parse_datetime(f["fields"]["Created"])
            vid = f["fields"]["Violation"][0]
            if vid not in latest_fee or latest_fee[vid] < d:
                latest_fee[vid] = d
    if now is None:
        now = tznow()

    # Discard time information; compare dates only
    now = now.replace(hour=0, minute=0, second=0)
    latest_fee = {
        k: v.replace(hour=0, minute=0, second=0) for k, v in latest_fee.items()
    }
    for v in violations:
        fee = v["fields"].get("Daily Fee")
        onset = safe_parse_datetime(v["fields"]["Onset"]).replace(
            hour=0, minute=0, second=0
        )
        if fee is None or fee == 0:
            continue
        t = latest_fee.get(v["id"], onset) + datetime.timedelta(days=1)
        tr = v["fields"].get("Close date (from Closure)")
        if tr is not None:
            tr = safe_parse_datetime(tr[0])
        while t <= now and (tr is None or t <= tr):
            fees.append((v["id"], fee, t.strftime("%Y-%m-%d")))
            t += datetime.timedelta(days=1)
    return fees


def update_accruals(fees=None):
    """Update accrual column for every violation that has a fee in the Fees table.
    Note this doesn't update violations for which there are no Fees"""
    totals = defaultdict(int)
    if fees is None:
        fees = airtable.get_policy_fees()
    for f in fees:
        if len(f["fields"]["Violation"]) > 0 and not f["fields"].get("Paid"):
            totals[f["fields"]["Violation"][0]] += f["fields"]["Amount"]

    for vid, accrued in totals.items():
        log.debug(f"Update violation {vid}; accrued ${accrued}")
        airtable.apply_violation_accrual(vid, accrued)
    return totals


NEW_VIOLATION_THRESH_HOURS = 18


def gen_comms_for_violation(  # pylint: disable=too-many-arguments
    v, old_accrued, new_accrued, sections, fname, email
):
    """Notify members of new violations and update them on active violations"""
    fields = v["fields"]
    if fields.get("Closure"):
        return None  # Resolved violation, nothing to do here
    if not fields.get("Onset"):
        return None  # Incomplete record
    onset = safe_parse_datetime(fields["Onset"])
    now = tznow()
    is_new_violation = old_accrued == 0 and onset > now - datetime.timedelta(
        hours=NEW_VIOLATION_THRESH_HOURS
    )
    return Msg.tmpl(
        "violation_started" if is_new_violation else "violation_ongoing",
        firstname=fname,
        start=onset,
        sections=sections,
        accrued=old_accrued + new_accrued,
        notes=fields["Notes"],
        fee=fields["Daily Fee"],
        target=email,
        id=f"violation#{v['id']}",
    )


def gen_comms(violations, old_fees, new_fees):
    """Generate comms for inbound fees"""
    result = []
    section_map = {
        s["id"]: s["fields"]["Section"] for s in airtable.get_policy_sections()
    }
    # Email users with new fees and violations
    for v in violations:
        old_accrued = sum(f[1] for f in old_fees if f[0] == v["id"])
        new_accrued = sum(f[1] for f in new_fees if f[0] == v["id"])
        sections = [section_map[s] for s in v["fields"]["Relevant Sections"]]
        neon_id = v["fields"].get("Neon ID")
        if neon_id is not None:
            acct = neon_base.fetch_account(neon_id, required=True)
            result.append(
                gen_comms_for_violation(
                    v,
                    old_accrued,
                    new_accrued,
                    sections,
                    fname=acct.fname,
                    email=acct.email,
                )
            )

    # Also send a summary of violations/fees to Discord #storage
    fees = airtable.get_policy_fees()
    result.append(enforcement_summary(violations, fees, target="#storage"))
    return [r for r in result if r is not None]
