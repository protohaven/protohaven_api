"""Policy enforcement methods for ensuring proper handling of
storage, equipment damage, and other violations"""

import datetime
import logging
from collections import defaultdict

from dateutil import parser as dateparser

from protohaven_api.config import tz, tznow
from protohaven_api.integrations import airtable, neon
from protohaven_api.integrations.comms import Msg

VIOLATION_MAX_AGE_DAYS = 90
SUSPENSION_MAX_AGE_DAYS = 365
MAX_VIOLATIONS_BEFORE_SUSPENSION = 3
SUSPENSION_DAYS_INITIAL = 30
SUSPENSION_DAYS_INCREMENT = 60
OPEN_VIOLATION_GRACE_PD_DAYS = 14


log = logging.getLogger("policy_enforcement.enforcer")


def enforcement_summary(violations, fees, new_sus, target):
    """Generate a summary of violation and suspension state, if there is any"""
    # Make sure we're only looking at open/unresolved policy stuff
    violations = [v for v in violations if not v["fields"].get("Closure")]
    new_sus = [f for f in new_sus if not f["fields"].get("Reinstated")]
    fees = [f for f in fees if not f["fields"].get("Paid")]
    if len(violations) == 0 and len(fees) == 0 and len(new_sus) == 0:
        return None

    # Condense violation and fee info into a list of updates
    vs = {}
    for v in violations:
        vs[v["id"]] = {
            "onset": dateparser.parse(v["fields"]["Onset"]),
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

    ss = {}
    for s in new_sus:
        ss[s["id"]] = {
            "start": dateparser.parse(s["fields"]["Start Date"]),
            "end": dateparser.parse(s["fields"]["End Date"])
            if s["fields"].get("End Date")
            else "fees paid",
        }

    if len(vs) == 0 and len(ss) == 0:
        return None

    return Msg.tmpl(
        "enforcement_summary",
        vs=vs.values(),
        ss=ss.values(),
        target=target,
    )


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
            d = dateparser.parse(f["fields"]["Created"]).astimezone(tz)
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
        onset = dateparser.parse(v["fields"]["Onset"]).replace(
            hour=0, minute=0, second=0
        )
        if fee is None or fee == 0:
            continue
        t = latest_fee.get(v["id"], onset) + datetime.timedelta(days=1)
        tr = v["fields"].get("Close date (from Closure)")
        if tr is not None:
            tr = dateparser.parse(tr[0]).astimezone(tz)
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


def _tally_violations(violations, suspensions, now):
    """Count up violations per neon ID, both before and after their most
    recent suspension (if any).

    Violations occurring before VIOLATION_MAX_AGE_DAYS are not counted."""
    date_thresh = now - datetime.timedelta(days=VIOLATION_MAX_AGE_DAYS)
    latest_suspension = {}
    for s in suspensions:
        if not s["fields"].get("End Date"):
            continue  # Happens if the suspensions row is blank/empty
        end = dateparser.parse(s["fields"]["End Date"])
        nid = s["fields"]["Neon ID"]
        if not latest_suspension.get(nid) or latest_suspension[nid] < end:
            latest_suspension[nid] = end

    counts = defaultdict(
        lambda: {
            "before_susp": 0,
            "after_susp": 0,
            "suspended": False,
            "violations": [],
        }
    )
    grace_pd = None

    # Make sure violations are in sorted order, so grace
    # periods can be properly applied
    violations.sort(key=lambda v: dateparser.parse(v["fields"]["Onset"]))

    for v in violations:
        nid = v["fields"].get("Neon ID")
        onset = dateparser.parse(v["fields"]["Onset"]).astimezone(tz)
        resolution = None
        if v["fields"].get("Closure"):
            resolution = dateparser.parse(
                v["fields"]["Close date (from Closure)"][0]
            ).astimezone(tz)

        assert date_thresh.tzinfo is not None
        assert onset is None or onset.tzinfo is not None
        assert grace_pd is None or grace_pd.tzinfo is not None
        if (
            nid is None
            or onset < date_thresh
            or (grace_pd is not None and onset < grace_pd)
        ):
            log.debug(f"Skip violation: {grace_pd} {onset} {date_thresh}")
            continue
        susp = latest_suspension.get(v["fields"].get("Neon ID"))
        if susp:
            counts[nid]["suspended"] = True
            if onset < susp:
                counts[nid]["before_susp"] += 1
            else:
                counts[nid]["after_susp"] += 1
        else:
            counts[nid]["before_susp"] += 1
        counts[nid]["violations"].append(v)
        if not resolution:
            grace_pd = onset + datetime.timedelta(days=OPEN_VIOLATION_GRACE_PD_DAYS)
        else:
            grace_pd = resolution
    return counts


def next_suspension_duration(suspensions, now):
    """Get a lookup dict of the duration of the next suspension for each
    Neon ID, defaulting to initial suspension time and increasing for
    each subsequent suspension within the TTL"""
    date_thresh = now - datetime.timedelta(days=SUSPENSION_MAX_AGE_DAYS)
    result = defaultdict(lambda: SUSPENSION_DAYS_INITIAL)
    for s in suspensions:
        end = dateparser.parse(s["fields"].get("End Date"))
        if end > date_thresh:
            result[s["fields"]["Neon ID"]] += SUSPENSION_DAYS_INCREMENT
    return result


def gen_suspensions(violations=None, suspensions=None, now=None):
    """Returns a list of calculated suspension actions based on each Neon ID's
    prior history of violations and suspensions."""
    if violations is None:
        violations = airtable.get_policy_violations()
    if suspensions is None:
        suspensions = airtable.get_policy_suspensions()
    if now is None:
        now = tznow()

    counts = _tally_violations(violations, suspensions, now)
    durations = next_suspension_duration(suspensions, now)
    result = []
    for nid, cc in counts.items():
        vs = [v["id"] for v in cc["violations"]]
        if (
            not cc["suspended"]
            and cc["before_susp"] >= MAX_VIOLATIONS_BEFORE_SUSPENSION
        ):
            result.append((nid, durations[nid], vs))
        elif (
            cc["suspended"]
            and cc["before_susp"] >= MAX_VIOLATIONS_BEFORE_SUSPENSION
            and cc["after_susp"] > 0
        ):
            result.append((nid, durations[nid], vs))
    return result


NEW_VIOLATION_THRESH_HOURS = 18


def gen_comms_for_violation(v, old_accrued, new_accrued, sections, member):
    """Notify members of new violations and update them on active violations"""
    fields = v["fields"]
    if fields.get("Closure"):
        return None  # Resolved violation, nothing to do here
    if not fields.get("Onset"):
        return None  # Incomplete record
    onset = dateparser.parse(fields["Onset"]).astimezone(tz)
    now = tznow()

    if old_accrued == 0 and onset > now - datetime.timedelta(
        hours=NEW_VIOLATION_THRESH_HOURS
    ):  # New violation, no fees accrued
        return Msg.tmpl(
            "violation_started",
            firstname=member["firstName"],
            start=onset,
            sections=sections,
            notes=fields["Notes"],
            fee=fields["Daily Fee"],
            target=member["email1"],
            id=f"violation#{v['id']}",
        )
    # Ongoing violation with accrued fees
    return Msg.tmpl(
        "violation_ongoing",
        firstname=member["firstName"],
        start=onset,
        sections=sections,
        notes=fields["Notes"],
        accrued=old_accrued + new_accrued,
        fee=fields["Daily Fee"],
        target=member["email1"],
        id=f"violation#{v['id']}",
    )

    ## else fields.get("Daily Fee", 0) == 0
    # return ecomms.violation_started(
    #    member["firstName"], onset_str, sections, fields["Notes"], 0
    # )


def gen_comms_for_suspension(sus, accrued, member):
    """Create comms to newly suspended users"""
    fields = sus["fields"]
    start = dateparser.parse(fields["Start Date"]).astimezone(tz)
    end = None
    if fields.get("End Time"):
        end = dateparser.parse(fields["End Date"]).astimezone(tz)
    suffix = ""
    if accrued > 0:
        suffix += " until fees are paid"
    elif end:
        suffix += f" until {end}"
    return Msg.tmpl(
        "suspension_started",
        firstname=member["firstName"],
        start=start,
        accrued=accrued,
        suffix=suffix,
        target=member["email1"],
        id=f"suspension{sus['fields']['Instance #']}",
    )


def gen_comms(
    violations, old_fees, new_fees, new_sus
):  # pylint: disable=too-many-locals
    """Generate comms for inbound fees and suspensions"""
    result = []
    section_map = {
        s["id"]: s["fields"]["Section"] for s in airtable.get_policy_sections()
    }
    violation_map = {v["id"]: v["fields"] for v in violations}
    # Email users with new fees and violations
    for v in violations:
        old_accrued = sum(f[1] for f in old_fees if f[0] == v["id"])
        new_accrued = sum(f[1] for f in new_fees if f[0] == v["id"])
        sections = [section_map[s] for s in v["fields"]["Relevant Sections"]]
        neon_id = v["fields"].get("Neon ID")
        if neon_id is not None:
            member = neon.fetch_account(neon_id)
            if member is None:
                raise RuntimeError("No member found for neon ID " + str(neon_id))
            member = member.get("individualAccount", member["companyAccount"])[
                "primaryContact"
            ]
            result.append(
                gen_comms_for_violation(v, old_accrued, new_accrued, sections, member)
            )

    # For each new suspension, build an admin email mentioning the suspension steps
    # Also build an email to the suspended user notifying of suspension
    # i.e. no Suspended bool column checked
    for sus in new_sus:
        if not sus["fields"]["Neon ID"]:
            raise RuntimeError("Suspension without Neon ID: " + str(sus))
        member = neon.fetch_account(sus["fields"]["Neon ID"])
        member = member.get("individualAccount", member["companyAccount"])[
            "primaryContact"
        ]
        violations = [violation_map[v] for v in sus["fields"]["Relevant Violations"]]
        sections = {section_map[s] for v in violations for s in v["Relevant Sections"]}
        accrued = sum(
            f[1] for f in old_fees if f[0] in sus["fields"]["Relevant Violations"]
        )
        accrued += sum(
            f[1] for f in new_fees if f[0] in sus["fields"]["Relevant Violations"]
        )
        result.append(
            gen_comms_for_suspension(  # pylint: disable=too-many-function-args
                sus, sections, accrued, member
            )
        )

        result.append(
            Msg.tmpl(
                "admin_create_suspension",
                neon_id=sus["fields"]["Neon ID"],
                end=sus["fields"]["End Date"],
                target="membership@protohaven.org",
                id=f"suspension{sus['fields']['Instance #']}",
            )
        )

    # Also send a summary of violations/fees/suspensions to Discord #storage
    fees = airtable.get_policy_fees()
    result.append(enforcement_summary(violations, fees, new_sus, target="#storage"))
    return [r for r in result if r is not None]
