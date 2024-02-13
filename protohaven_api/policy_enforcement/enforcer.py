"""Policy enforcement methods for ensuring proper handling of
storage, equipment damage, and other violations"""

import datetime
import logging
from collections import defaultdict

import pytz
from dateutil import parser as dateparser

from protohaven_api.integrations import airtable, neon
from protohaven_api.policy_enforcement import comms as ecomms

VIOLATION_MAX_AGE_DAYS = 90
SUSPENSION_MAX_AGE_DAYS = 365
MAX_VIOLATIONS_BEFORE_SUSPENSION = 3
SUSPENSION_DAYS_INITIAL = 30
SUSPENSION_DAYS_INCREMENT = 60
OPEN_VIOLATION_GRACE_PD_DAYS = 14

tz = pytz.timezone("EST")

log = logging.getLogger("policy_enforcement.enforcer")


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
            d = (
                dateparser.parse(f["fields"]["Created"])
                .astimezone(tz)
                .replace(hour=0, minute=0, second=0)
            )
            vid = f["fields"]["Violation"][0]
            if vid not in latest_fee or latest_fee[vid] < d:
                latest_fee[vid] = d
    if now is None:
        now = datetime.datetime.now().astimezone(tz)

    for v in violations:
        fee = v["fields"].get("Daily Fee")
        if fee is None or fee == 0:
            continue
        t = latest_fee.get(
            v["id"], dateparser.parse(v["fields"]["Onset"])
        ) + datetime.timedelta(days=1)
        tr = v["fields"].get("Resolution")
        if tr is not None:
            tr = dateparser.parse(tr).astimezone(tz)
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
        onset = dateparser.parse(v["fields"]["Onset"])
        resolution = None
        if v["fields"].get("Resolution"):
            resolution = dateparser.parse(v["fields"]["Resolution"])
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
        now = datetime.datetime.now().astimezone(tz)

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
    if fields.get("Resolution"):
        return None  # Resolved violation, nothing to do here
    if not fields.get("Onset"):
        return None  # Incomplete record
    onset = dateparser.parse(fields["Onset"]).astimezone(tz)
    onset_str = onset.strftime("%Y-%m-%d")
    now = datetime.datetime.now().astimezone(tz)

    if old_accrued == 0 and onset > now - datetime.timedelta(
        hours=NEW_VIOLATION_THRESH_HOURS
    ):  # New violation, no fees accrued
        return ecomms.violation_started(
            member["firstName"],
            onset_str,
            sections,
            fields["Notes"],
            fields["Daily Fee"],
        )
    # Ongoing violation with accrued fees
    return ecomms.violation_ongoing(
        member["firstName"],
        onset_str,
        sections,
        fields["Notes"],
        old_accrued + new_accrued,
        fields["Daily Fee"],
    )

    ## else fields.get("Daily Fee", 0) == 0
    # return ecomms.violation_started(
    #    member["firstName"], onset_str, sections, fields["Notes"], 0
    # )


def gen_comms_for_suspension(sus, accrued, member):
    """Create comms to newly suspended users"""
    fields = sus["fields"]
    start = dateparser.parse(fields["Start Date"]).astimezone(tz).strftime("%Y-%m-%d")
    end = None
    if fields.get("End Time"):
        end = dateparser.parse(fields["End Date"]).astimezone(tz).strftime("%Y-%m-%d")
    return ecomms.suspension_started(member["firstName"], start, accrued, end)


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
            member = member.get("individualAccount", member["companyAccount"])[
                "primaryContact"
            ]
            c = gen_comms_for_violation(v, old_accrued, new_accrued, sections, member)
            if c is not None:
                result.append(
                    {
                        "target": member["email1"],
                        "subject": c[0],
                        "body": c[1],
                        "id": f"violation#{v['id']}",
                    }
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
        (
            subject,
            body,
        ) = gen_comms_for_suspension(  # pylint: disable=too-many-function-args
            sus, sections, accrued, member
        )
        result.append(
            {
                "target": member["email1"],
                "subject": subject,
                "body": body,
                "id": f"suspension{sus['fields']['Instance #']}",
            }
        )

        subject, body = ecomms.admin_create_suspension(
            sus["fields"]["Neon ID"], sus["fields"]["End Date"]
        )
        result.append(
            {
                "target": "membership@protohaven.org",
                "subject": subject,
                "body": body,
                "id": f"suspension{sus['fields']['Instance #']}",
            }
        )

    # Also send a summary of violations/fees/suspensions to Discord #storage
    fees = airtable.get_policy_fees()
    subject, body = ecomms.enforcement_summary(violations, fees, new_sus)
    result.append({"target": "#storage", "subject": subject, "body": body, "id": None})
    return result
