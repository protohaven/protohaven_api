"""Message template functions for notifying instructors, techs, and event registrants"""

from dateutil import parser as dateparser
from jinja2 import Environment, PackageLoader, select_autoescape

env = Environment(
    loader=PackageLoader("protohaven_api.policy_enforcement"),
    autoescape=select_autoescape(),
)


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

    subject = "Violations and Actions Summary"
    return subject, env.get_template("enforcement_summary.jinja2").render(
        vs=vs.values(), outstanding=outstanding, ss=ss.values()
    )


def admin_create_suspension(neon_id, end):
    """Message for staff/admin to carry out suspension actions for a member"""
    subject = f"ACTION REQUIRED: Suspend Protohaven member {neon_id} until {end}"
    return subject, env.get_template("admin_create_suspension.jinja2").render(
        neon_id=neon_id, end=end
    )


def suspension_ended(firstname):
    """Message to member that their suspension is over"""
    subject = f"{firstname}: your Protohaven membership has been reinstated"
    return subject, env.get_template("suspension_ended.jinja2").render(
        firstname=firstname
    )


def suspension_started(firstname, start, accrued, end=None):
    """Message to member that their membership is suspended"""
    subject = f"{firstname}: your Protohaven membership has been suspended"
    if accrued > 0:
        subject += " until fees are paid"
    elif end:
        subject += f" until {end}"
    return subject, env.get_template("suspension_started.jinja2").render(
        firstname=firstname, start=start, accrued=accrued
    )


def violation_ongoing(
    firstname, start, sections, notes, accrued, fee
):  # pylint: disable=too-many-arguments
    """Message to member about ongoing violation accruing fees"""
    if accrued > 0:
        subject = (
            f"{firstname}: ongoing Protohaven violation has accrued ${accrued} in fees"
        )
    else:
        subject = f"{firstname}: ongoing Protohaven violation"
    return subject, env.get_template("violation_ongoing.jinja2").render(
        firstname=firstname,
        start=start,
        sections=sections,
        notes=notes,
        accrued=accrued,
        fee=fee,
    )


def violation_started(firstname, start, sections, notes, fee):
    """Message to member that a new violation was issued"""
    subject = f"{firstname}: new Protohaven violation issued for {start}"
    return subject, env.get_template("violation_started.jinja2").render(
        firstname=firstname, start=start, sections=sections, notes=notes, fee=fee
    )


def violation_ended(firstname, start, end):
    """Message to member that the violation has been resolved/ended"""
    raise NotImplementedError("TODO")


def admin_suspension_reminder(neon_id, end_date):
    """Message to admin reminding them to issue suspension to member"""
    raise NotImplementedError("TODO")
