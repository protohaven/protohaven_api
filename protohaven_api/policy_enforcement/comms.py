"""Message template functions for notifying instructors, techs, and event registrants"""

from dateutil import parser as dateparser

from protohaven_api.comms_templates import render


def enforcement_summary(violations, fees, new_sus):
    """Generate a summary of violation and suspension state, if there is any"""
    # Make sure we're only looking at open/unresolved policy stuff
    violations = [v for v in violations if not v["fields"].get("Closure")]
    new_sus = [f for f in new_sus if not f["fields"].get("Reinstated")]
    fees = [f for f in fees if not f["fields"].get("Paid")]
    if len(violations) == 0 and len(fees) == 0 and len(new_sus) == 0:
        return None, None

    # Condense violation and fee info into a list of updates
    vs = {}
    outstanding = 0
    for v in violations:
        vs[v["id"]] = {
            "onset": dateparser.parse(v["fields"]["Onset"]).strftime("%Y-%m-%d"),
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
        else:
            outstanding += amt

    ss = {}
    for s in new_sus:
        ss[s["id"]] = {
            "start": dateparser.parse(s["fields"]["Start Date"]).strftime("%Y-%m-%d"),
            "end": dateparser.parse(s["fields"]["End Date"]).strftime("%Y-%m-%d")
            if s["fields"].get("End Date")
            else "fees paid",
        }

    if len(vs) == 0 and len(ss) == 0 and outstanding == 0:
        return None, None

    return render(
        "enforcement_summary", vs=vs.values(), outstanding=outstanding, ss=ss.values()
    )


def admin_create_suspension(neon_id, end):
    """Message for staff/admin to carry out suspension actions for a member"""
    return render("admin_create_suspension", neon_id=neon_id, end=end)


def suspension_ended(firstname):
    """Message to member that their suspension is over"""
    return render("suspension_ended", firstname=firstname)


def suspension_started(firstname, start, accrued, end=None):
    """Message to member that their membership is suspended"""
    suffix = ""
    if accrued > 0:
        suffix += " until fees are paid"
    elif end:
        suffix += f" until {end}"
    return render(
        "suspension_started",
        firstname=firstname,
        start=start,
        accrued=accrued,
        suffix=suffix,
    )


def violation_ongoing(
    firstname, start, sections, notes, accrued, fee
):  # pylint: disable=too-many-arguments
    """Message to member about ongoing violation accruing fees"""
    return render(
        "violation_ongoing",
        firstname=firstname,
        start=start,
        sections=sections,
        notes=notes,
        accrued=accrued,
        fee=fee,
    )


def violation_started(firstname, start, sections, notes, fee):
    """Message to member that a new violation was issued"""
    return render(
        "violation_started",
        firstname=firstname,
        start=start,
        sections=sections,
        notes=notes,
        fee=fee,
    )


def violation_ended(firstname, start, end):
    """Message to member that the violation has been resolved/ended"""
    raise NotImplementedError("TODO")


def admin_suspension_reminder(neon_id, end_date):
    """Message to admin reminding them to issue suspension to member"""
    raise NotImplementedError("TODO")
