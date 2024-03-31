"""Handlers for instructor actions on classes"""
import datetime
from collections import defaultdict

from dateutil import parser as dateparser
from flask import Blueprint, redirect, render_template, request
from flask_cors import cross_origin

from protohaven_api.config import tz
from protohaven_api.handlers.auth import user_email
from protohaven_api.integrations import airtable, neon, schedule
from protohaven_api.rbac import Role, get_roles, require_login_role

page = Blueprint("instructor", __name__, template_folder="templates")


HIDE_UNCONFIRMED_DAYS_AHEAD = 10
HIDE_CONFIRMED_DAYS_AFTER = 10


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


def _get_instructor_readiness(inst, teachable_classes=None, instructor_schedules=None):
    """Returns a list of actoin sinstructors need to take to be fully onboarded.
    Note: `inst` is a neon result requiring Account Current Membership Status"""
    result = {
        "neon_id": None,
        "fullname": "unknown",
        "active_membership": "inactive",
        "discord_user": "missing",
        "capabilities_listed": "missing",
        "in_calendar": "missing",
    }
    result["neon_id"] = inst["Account ID"]
    if inst["Account Current Membership Status"] == "Active":
        result["active_membership"] = "OK"
    else:
        result["active_membership"] = inst["Account Current Membership Status"]
    if inst.get("Discord User"):
        result["discord_user"] = "OK"
    result["fullname"] = f"{inst['First Name']} {inst['Last Name']}".strip()

    if not teachable_classes:
        teachable_classes = airtable.fetch_instructor_teachable_classes()
    print("Teachable classes:", teachable_classes)
    if len(teachable_classes.get(result["fullname"].lower(), [])) > 0:
        result["capabilities_listed"] = "OK"

    now = datetime.datetime.now()
    if not instructor_schedules:
        instructor_schedules = schedule.fetch_instructor_schedules(
            now - datetime.timedelta(days=90), now + datetime.timedelta(days=90)
        )
    if result["fullname"] in instructor_schedules.keys():
        result["in_calendar"] = "OK"
    return result


@page.route("/instructor/class/attendees")
@require_login_role(Role.INSTRUCTOR)
@cross_origin()
def instructor_class_attendees():
    """Gets the attendees for a given class, by its neon ID"""
    event_id = request.args.get("id")
    if event_id is None:
        raise RuntimeError("Requires param id")
    result = list(neon.fetch_attendees(event_id))
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


def get_dashboard_schedule_sorted(email):
    """Fetches the instructor availability schedule for an individual instructor.
    Excludes unconfirmed classes sooner than HIDE_UNCONFIRMED_DAYS_AHEAD
    as well as confirmed classes older than HIDE_CONFIRMED_DAYS_AFTER"""
    sched = []
    now = datetime.datetime.now().astimezone(tz)
    age_out_thresh = now - datetime.timedelta(days=HIDE_CONFIRMED_DAYS_AFTER)
    confirmation_thresh = now + datetime.timedelta(days=HIDE_UNCONFIRMED_DAYS_AHEAD)
    for s in airtable.get_class_automation_schedule():
        if s["fields"]["Email"].lower() != email:
            continue

        start_date = dateparser.parse(s["fields"]["Start Time"]).astimezone(tz)
        end_date = start_date + datetime.timedelta(
            days=7 * (s["fields"]["Days (from Class)"][0] - 1)
        )
        confirmed = s["fields"].get("Confirmed", None) is not None
        if confirmed and end_date <= age_out_thresh:
            continue
        if not confirmed and start_date <= confirmation_thresh:
            continue

        s["fields"]["_id"] = s["id"]
        sched.append([s["id"], s["fields"]])

    sched.sort(key=lambda s: s[1]["Start Time"])
    return sched


# TODO @require_login_role(Role.INSTRUCTOR)
@page.route("/instructor/about")
@cross_origin()
def instructor_about():
    email = request.args.get("email")
    if email is not None:
        # TODO
        # roles = get_roles()
        # if roles is None or Role.ADMIN["name"] not in roles:
        #    return "Not Authorized"
        pass
    else:
        email = user_email()
    return _get_instructor_readiness(neon.search_member(email.lower()))


# TODO
# @require_login_role(Role.INSTRUCTOR)
@page.route("/instructor/class")
@cross_origin()
def instructor_class():
    """Display all class information about a particular instructor (via email)"""
    email = request.args.get("email")
    if email is not None:
        # TODO
        # roles = get_roles()
        # if roles is None or Role.ADMIN["name"] not in roles:
        #    return "Not Authorized"
        pass
    else:
        email = user_email()
    email = email.lower()
    sched = get_dashboard_schedule_sorted(email)
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
                clearances=e.get("Form Name (from Clearance) (from Class)", ["n/a"]),
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

    # Look up the name on file in the capabilities list - this is used to match
    # on manually entered calendar availability
    caps_name = {v: k for k, v in airtable.get_instructor_email_map().items()}.get(
        email, "<NOT FOUND>"
    )

    return {
        "schedule": sched,
        "now": datetime.datetime.now(),
        "email": email,
        "name": caps_name,
    }


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


@page.route("/instructor/readiness", methods=["GET"])
def instructors_status():
    """Get the onboarding status of all instructors"""

    results = defaultdict(
        lambda: {
            "neon_id": None,
            "fullname": "unknown",
            "active_membership": "inactive",
            "discord_user": "missing",
            "capabilities_listed": "missing",
            "in_calendar": "missing",
        }
    )

    neon_instructors = neon.get_members_with_role(
        Role.INSTRUCTOR,
        [
            "Account Current Membership Status",
            "Email 1",
            neon.CUSTOM_FIELD_DISCORD_USER,
        ],
    )
    now = datetime.datetime.now()
    teachable_classes = airtable.fetch_instructor_teachable_classes()
    instructor_schedules = schedule.fetch_instructor_schedules(
        now - datetime.timedelta(days=90), now + datetime.timedelta(days=90)
    )
    for inst in neon_instructors:
        e = inst["Email 1"].lower()
        results[e] = _get_instructor_readiness(
            inst, teachable_classes, instructor_schedules
        )

    render = []
    for k, v in results.items():
        v["email"] = k
        render.append(v)
    render.sort(key=lambda e: int(e["neon_id"]))
    return render_template("instructor_readiness.html", results=render)
