"""Policy enforcement methods for ensuring proper handling of
storage, equipment damage, and other violations"""

import datetime
from collections import defaultdict

from dateutil import parser as dateparser

from protohaven_api.integrations import airtable

VIOLATION_MAX_AGE_DAYS = 90
SUSPENSION_MAX_AGE_DAYS = 365
MAX_VIOLATIONS_BEFORE_SUSPENSION = 3
SUSPENSION_DAYS_INITIAL = 30
SUSPENSION_DAYS_INCREMENT = 60
OPEN_VIOLATION_GRACE_PD_DAYS = 14


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
            d = dateparser.parse(f["fields"]["Created"])
            vid = f["fields"]["Violation"][0]
            if vid not in latest_fee or latest_fee[vid] < d:
                latest_fee[vid] = d
    if now is None:
        now = datetime.datetime.now()

    for v in violations:
        fee = v["fields"].get("Daily Fee")
        if fee is None or fee == 0:
            continue
        t = latest_fee.get(
            v["id"], dateparser.parse(v["fields"]["Onset"])
        ) + datetime.timedelta(days=1)
        tr = v["fields"].get("Resolution")
        if tr is not None:
            tr = dateparser.parse(tr)
        while t <= now and (tr is None or t <= tr):
            fees.append((v["id"], fee, t))
            t += datetime.timedelta(days=1)
    return fees


def _tally_violations(violations, suspensions, now):
    """Count up violations per neon ID, both before and after their most
    recent suspension (if any).

    Violations occurring before VIOLATION_MAX_AGE_DAYS are not counted."""
    date_thresh = now - datetime.timedelta(days=VIOLATION_MAX_AGE_DAYS)
    latest_suspension = {}
    for s in suspensions:
        end = dateparser.parse(s["fields"]["End Date"])
        nid = s["fields"]["Neon ID"]
        if not latest_suspension.get(nid) or latest_suspension[nid] < end:
            latest_suspension[nid] = end

    counts = defaultdict(
        lambda: {"before_susp": 0, "after_susp": 0, "suspended": False}
    )
    grace_pd = None

    # Make sure violations are in sorted order, so grace
    # periods can be properly applied
    violations.sort(key=lambda v: dateparser.parse(v["fields"]["Onset"]))

    for v in violations:
        nid = v["fields"].get("Neon ID")
        onset = dateparser.parse(v["fields"]["Onset"])
        resolution = None
        if v["fields"]["Resolution"]:
            resolution = dateparser.parse(v["fields"]["Resolution"])
        if (
            nid is None
            or onset < date_thresh
            or (grace_pd is not None and onset < grace_pd)
        ):
            print("Skip violation:", grace_pd, onset, date_thresh)
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

    counts = _tally_violations(violations, suspensions, now)
    durations = next_suspension_duration(suspensions, now)
    result = []
    for nid, cc in counts.items():
        if (
            not cc["suspended"]
            and cc["before_susp"] >= MAX_VIOLATIONS_BEFORE_SUSPENSION
        ):
            result.append((nid, durations[nid]))
        elif (
            cc["suspended"]
            and cc["before_susp"] >= MAX_VIOLATIONS_BEFORE_SUSPENSION
            and cc["after_susp"] > 0
        ):
            result.append((nid, durations[nid]))
    return result
