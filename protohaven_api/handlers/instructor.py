"""Handlers for instructor actions on classes"""
import datetime

import pytz
from dateutil import parser as dateparser
from flask import Blueprint, redirect, render_template, request

from protohaven_api.handlers.auth import user_email
from protohaven_api.integrations import airtable, neon
from protohaven_api.rbac import Role, get_roles, require_login_role

page = Blueprint("instructor", __name__, template_folder="templates")


def prefill_form(  # pylint: disable=too-many-arguments,too-many-locals
    instructor,
    start_date,
    hours,
    class_name,
    pass_emails,
    clearances,
    volunteer,
    event_id,
):
    """Return prefilled instructor log submission form"""
    individual = airtable.get_instructor_log_tool_codes()
    clearance_codes = []
    tool_codes = []
    for c in clearances:
        if c in individual:
            tool_codes.append(c)
        else:
            clearance_codes.append(c)

    start_yyyy_mm_dd = start_date.strftime("%Y-%m-%d")
    result = (
        "https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-"
        + "Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform?usp=pp_url"
    )
    result += f"&entry.1719418402={instructor}"
    result += f"&entry.1405633595={start_yyyy_mm_dd}"
    result += f"&entry.1276102155={hours}"
    result += f"&entry.654625226={class_name}"
    if volunteer:
        result += "&entry.1406934632=Yes,+please+donate+my+time."
    result += "&entry.362496408=Nope,+just+a+single+session+class"
    result += f"&entry.204701066={', '.join(pass_emails)}"
    for cc in clearance_codes:
        result += f"&entry.965251553={cc}"
    result += f"&entry.1116111507={'Yes' if len(tool_codes) > 0 else 'No'}"
    result += f"&entry.1646535924={event_id}"
    for tc in tool_codes:
        result += f"&entry.1725748243={tc}"
    return result


@page.route("/instructor/class/attendees")
@require_login_role(Role.INSTRUCTOR)
def instructor_class_attendees():
    """Gets the attendees for a given class, by its neon ID"""
    event_id = request.args.get("id")
    if event_id is None:
        raise RuntimeError("Requires param id")
    result = neon.fetch_attendees(event_id)
    for a in result:
        if a["accountId"]:
            acc = neon.fetch_account(a["accountId"])
            if acc is not None:
                a["email"] = acc.get("individualAccount", acc.get("companyAccount"))[
                    "primaryContact"
                ]["email1"]

    return result


@page.route("/instructor/class_selector")
def instructor_class_selector():
    """Used previously. This redirects to the new endpoint"""
    return redirect("/instructor/class")


@page.route("/instructor/class")
@require_login_role(Role.INSTRUCTOR)
def instructor_class():
    """Display all class information about a particular instructor (via email)"""
    email = request.args.get("email")
    if email is not None:
        roles = get_roles()
        if roles is None or Role.ADMIN["name"] not in roles:
            return "Not Authorized"
    else:
        email = user_email()
    email = email.lower()
    sched = []
    tz = pytz.timezone("US/Eastern")
    age_out_thresh = datetime.datetime.now().astimezone(tz) - datetime.timedelta(
        days=10
    )
    for s in airtable.get_class_automation_schedule():
        end_date = dateparser.parse(s["fields"]["Start Time"]).astimezone(
            tz
        ) + datetime.timedelta(days=7 * (s["fields"]["Days (from Class)"][0] - 1))
        if s["fields"]["Email"].lower() == email and end_date > age_out_thresh:
            s["fields"]["_id"] = s["id"]
            sched.append([s["id"], s["fields"]])
    sched.sort(key=lambda s: s[1]["Start Time"])
    for _, e in sched:
        date = dateparser.parse(e["Start Time"]).astimezone(tz)

        # If it's in neon, generate a log URL.
        # Placeholder for attendee names/emails as that's loaded
        # lazily on page load.
        if e.get("Neon ID"):
            e["prefill"] = prefill_form(
                instructor=e["Instructor"],
                start_date=date,
                hours=e["Hours (from Class)"][0],
                class_name=e["Name (from Class)"][0],
                pass_emails=["$ATTENDEE_NAMES"],
                clearances=e["Form Name (from Clearance) (from Class)"],
                volunteer=e.get("Volunteer", False),
                event_id=e["Neon ID"],
            )

        for date_field in ("Confirmed", "Instructor Log Date"):
            if e.get(date_field):
                e[date_field] = dateparser.parse(e[date_field])
        e["Dates"] = []
        for _ in range(e["Days (from Class)"][0]):
            e["Dates"].append(date.strftime("%A %b %-d, %-I%p"))
            date += datetime.timedelta(days=7)
    return render_template(
        "instructor_class.html",
        schedule=sched,
        now=datetime.datetime.now(),
        email=email,
    )


@page.route("/instructor/class/update", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_update():
    """Confirm or unconfirm a class to run, by the instructor"""
    eid = request.form.get("eid")
    pub = request.form.get("pub") == "true"
    return airtable.respond_class_automation_schedule(eid, pub).content


@page.route("/instructor/class/supply_req", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_supply_req():
    """Mark supplies as missing or confirmed for a class"""
    eid = request.form.get("eid")
    missing = request.form.get("missing") == "true"
    return airtable.mark_schedule_supply_request(eid, missing).content


@page.route("/instructor/class/volunteer", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_volunteer():
    """Change the volunteer state of a class"""
    eid = request.form.get("eid")
    v = request.form.get("volunteer") == "true"
    return airtable.mark_schedule_volunteer(eid, v).content
