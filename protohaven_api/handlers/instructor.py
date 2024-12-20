"""Handlers for instructor actions on classes"""
import datetime
import logging

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, redirect, request

from protohaven_api.automation.classes.scheduler import (
    generate_env as generate_scheduler_env,
)
from protohaven_api.automation.classes.scheduler import push_schedule, solve_with_env
from protohaven_api.config import tz, tznow
from protohaven_api.handlers.auth import user_email, user_fullname
from protohaven_api.integrations import airtable, neon, neon_base
from protohaven_api.rbac import Role, am_admin, require_login_role

log = logging.getLogger("handlers.instructor")

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


def get_instructor_readiness(inst, caps=None):
    """Returns a list of actions instructors need to take to be fully onboarded.
    Note: `inst` is a neon result requiring Account Current Membership Status"""
    result = {
        "neon_id": None,
        "email": "OK",
        "airtable_id": None,
        "fullname": "unknown",
        "active_membership": "inactive",
        "discord_user": "missing",
        "capabilities_listed": "missing",
        "paperwork": "unknown",
        "profile_img": None,
        "bio": None,
    }

    if len(inst) > 1:
        result["email"] = f"{len(inst)} duplicate accounts in Neon"
    inst = inst[0]

    result["neon_id"] = inst.get("Account ID")
    if inst["Account Current Membership Status"] == "Active":
        result["active_membership"] = "OK"
    else:
        result["active_membership"] = inst["Account Current Membership Status"]
    if inst.get("Discord User"):
        result["discord_user"] = "OK"
    result[
        "fullname"
    ] = f"{inst['First Name'].strip()} {inst['Last Name'].strip()}".strip()

    if not caps:
        caps = airtable.fetch_instructor_capabilities(result["fullname"])
    if caps:
        result["airtable_id"] = caps["id"]
        if len(caps["fields"].get("Class", [])) > 0:
            result["capabilities_listed"] = "OK"

        missing_info = [
            x
            for x in [
                "W9" if not caps["fields"].get("W9 Form") else None,
                "Direct Deposit"
                if not caps["fields"].get("Direct Deposit Info")
                else None,
                "Profile Pic" if not caps["fields"].get("Profile Pic") else None,
                "Bio" if not caps["fields"].get("Bio") else None,
            ]
            if x
        ]

        result["profile_img"] = caps["fields"].get("Profile Pic", [{"url": None}])[0][
            "url"
        ]
        result["bio"] = caps["fields"].get("Bio")
        if len(missing_info) > 0:
            result["paperwork"] = f"Missing {', '.join(missing_info)}"
        else:
            result["paperwork"] = "OK"

    return result


@page.route("/instructor/class/attendees")
@require_login_role(Role.INSTRUCTOR)
def instructor_class_attendees():
    """Gets the attendees for a given class, by its neon ID"""
    event_id = request.args.get("id")
    if event_id is None:
        return Response("Requires URL parameter 'id'", status=400)
    try:
        result = list(neon.fetch_attendees(event_id))
    except RuntimeError:
        log.warning(f"Failed to fetch event #{event_id}")
        result = []

    for a in result:
        if a["accountId"]:
            try:
                acc, _ = neon_base.fetch_account(a["accountId"])
                if acc is not None:
                    a["email"] = acc["primaryContact"]["email1"]
            except RuntimeError:
                pass

    return result


@page.route("/instructor/class")
def instructor_class_selector_redirect1():
    """Used previously. This redirects to the new endpoint"""
    return redirect("/instructor")


@page.route("/instructor/class_selector")
def instructor_class_selector_redirect2():
    """Used previously. This redirects to the new endpoint"""
    return redirect("/instructor")


def get_dashboard_schedule_sorted(email, now=None):
    """Fetches the instructor availability schedule for an individual instructor.
    Excludes unconfirmed classes sooner than HIDE_UNCONFIRMED_DAYS_AHEAD
    as well as confirmed classes older than HIDE_CONFIRMED_DAYS_AFTER"""
    sched = []
    if now is None:
        now = tznow()
    age_out_thresh = now - datetime.timedelta(days=HIDE_CONFIRMED_DAYS_AFTER)
    confirmation_thresh = now + datetime.timedelta(days=HIDE_UNCONFIRMED_DAYS_AHEAD)
    for s in airtable.get_class_automation_schedule():
        if s["fields"]["Email"].lower() != email or s["fields"].get("Rejected"):
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


@page.route("/instructor/about")
@require_login_role(Role.INSTRUCTOR)
def instructor_about():
    """Get readiness state of instructor"""
    email = request.args.get("email")
    if email is not None:
        ue = user_email()
        if ue != email and not am_admin():
            return Response("Access Denied for admin parameter `email`", status=401)
    else:
        email = user_email()
        if not email:
            return Response("You are not logged in.", status=401)
    inst = list(neon.search_member(email.lower()))
    if len(inst) == 0:
        return Response(
            f"Instructor data not found for email {email.lower()}", status=404
        )
    return get_instructor_readiness(inst)


def _annotate_schedule_class(e):
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
    return e


@page.route("/instructor")
@require_login_role(Role.INSTRUCTOR)
def instructor_class():
    """Return svelte compiled static page for instructor dashboard"""
    return current_app.send_static_file("svelte/instructor.html")


@page.route("/instructor/_app/immutable/<typ>/<path>")
def instructor_class_svelte_files(typ, path):
    """Return svelte compiled static page for instructor dashboard"""
    return current_app.send_static_file(f"svelte/_app/immutable/{typ}/{path}")


@page.route("/instructor/class_details")
@require_login_role(Role.INSTRUCTOR)
def instructor_class_details():
    """Display all class information about a particular instructor (via email)"""
    email = request.args.get("email")
    if email is not None:
        ue = user_email()
        if ue != email and not am_admin():
            return Response("Access Denied for admin parameter `email`", status=401)
    else:
        email = user_email()
    email = email.lower()
    sched = [
        (k, _annotate_schedule_class(e))
        for k, e in get_dashboard_schedule_sorted(email)
    ]

    # Look up the name on file in the capabilities list - this is used to match
    # on manually entered calendar availability
    caps_name = {v: k for k, v in airtable.get_instructor_email_map().items()}.get(
        email, "<NOT FOUND>"
    )

    return {
        "schedule": sched,
        "now": tznow(),
        "email": email,
        "name": caps_name,
    }


@page.route("/instructor/class/update", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_update():
    """Confirm or unconfirm a class to run, by the instructor"""
    data = request.json
    eid = data["eid"]
    pub = data["pub"]
    # print("eid", eid, "pub", pub)
    _, result = airtable.respond_class_automation_schedule(eid, pub)
    return _annotate_schedule_class(result["fields"])


@page.route("/instructor/class/supply_req", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_supply_req():
    """Mark supplies as missing or confirmed for a class"""
    data = request.json
    eid = data["eid"]
    missing = data["missing"]
    _, result = airtable.mark_schedule_supply_request(eid, missing)
    return _annotate_schedule_class(result["fields"])


@page.route("/instructor/class/volunteer", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_volunteer():
    """Change the volunteer state of a class"""
    data = request.json
    eid = data["eid"]
    v = data["volunteer"]
    _, result = airtable.mark_schedule_volunteer(eid, v)
    return _annotate_schedule_class(result["fields"])


@page.route("/instructor/setup_scheduler_env", methods=["GET"])
@require_login_role(Role.INSTRUCTOR)
def setup_scheduler_env():
    """Create a class scheduler environment to run"""
    try:
        return generate_scheduler_env(
            dateparser.parse(request.args.get("start")).astimezone(tz),
            dateparser.parse(request.args.get("end")).astimezone(tz)
            + datetime.timedelta(hours=24),  # End of final day
            [request.args.get("inst")],
        )
    except dateparser.ParserError:
        return Response(
            "Please select valid dates, with the start date before the end date",
            status=400,
        )
    except RuntimeError as e:
        return Response("Runtime error: " + str(e), status=400)


@page.route("/instructor/run_scheduler", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def run_scheduler():
    """Run the class scheduler with a specific environment"""
    result, score = solve_with_env(request.json)
    return {"result": result, "score": score}


@page.route("/instructor/push_classes", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def push_classes():
    """Push specific classes to airtable.
    2024-04-18: Note that this allows the instructor to push *any* classes at any time,
    which isn't super great. But the odds of misuse are pretty low presently
    so fine to ignore for now."""

    data = request.json
    if len(data) != 1:
        return Response(
            "push_classes requires exactly one instructor class set", status=400
        )

    fullname = list(data.keys())[0]
    ufn = user_fullname()
    if ufn != fullname and require_login_role(Role.ADMIN)(lambda: True)() is not True:
        return Response(
            f"Access Denied for pushing classes for instructor '{fullname}'", status=401
        )

    # We automatically confirm classes pushed via instructor dashboard since the instructor
    # is the one pushing the class.
    push_schedule(data, autoconfirm=True)
    return {"success": True}


@page.route("/instructor/class/neon_state", methods=["GET"])
@require_login_role(Role.INSTRUCTOR)
def class_neon_state():
    """Fetch the current state of the class in Neon"""
    event_id = request.args.get("id")
    if event_id is None:
        return Response("Requires URL parameter 'id'", status=400)
    return neon.fetch_event(event_id)


@page.route("/instructor/class/cancel", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def cancel_class():
    """Cancel a class - fails if anyone is registered for it"""
    data = request.json
    cid = data["neon_id"]
    num_attendees = len(list(neon.fetch_attendees(cid)))
    if num_attendees > 0:
        return Response(
            f"Unable to cancel class with {num_attendees} attendee(s). Contact "
            "education@protohaven.org or reach out to #instructors on discord to cancel this class",
            status=409,
        )

    log.warning(f"Cancelling class {cid}")
    neon.set_event_scheduled_state(cid, scheduled=False)
    return {"success": True}


def _safe_date(v):
    if v is None:
        return v
    return dateparser.parse(v).astimezone(tz)


@page.route("/instructor/calendar/availability", methods=["GET", "PUT", "DELETE"])
def inst_availability():
    """Different methods for CRUD actions on Availability records in airtable, used to
    describe an instructor's availability"""
    if request.method == "GET":
        inst = request.values.get("inst").lower()
        t0 = _safe_date(request.values.get("t0"))
        t1 = _safe_date(request.values.get("t1"))
        if not t0 or not t1:
            return Response(
                "Both t0 and t1 required in request to /instructor/calendar/availability",
                status=400,
            )
        t1 += datetime.timedelta(hours=24)  # End date is inclusive
        avail = list(airtable.get_instructor_availability(inst))

        expanded = list(airtable.expand_instructor_availability(avail, t0, t1))

        log.info(f"Expanded and merged availability: {expanded}")
        sched = [
            s
            for s in airtable.get_class_automation_schedule()
            if dateparser.parse(s["fields"]["Start Time"]) >= t0
            and not s["fields"].get("Rejected")
        ]
        return {
            "records": {r["id"]: r["fields"] for r in avail},
            "availability": expanded,
            "schedule": sched,
        }

    if request.method == "PUT":
        rec = request.json.get("rec")
        t0 = _safe_date(request.json.get("t0"))
        t1 = _safe_date(request.json.get("t1"))
        inst_id = request.json.get("inst_id")
        if not t0 or not t1:
            return Response(
                "t0, t1, inst_id required in json PUT to /instructor/calendar/availability",
                status=400,
            )
        recurrence = request.json.get("recurrence")
        if rec is not None:
            result = airtable.update_availability(rec, inst_id, t0, t1, recurrence)
        else:
            result = airtable.add_availability(inst_id, t0, t1, recurrence)
        log.info(f"PUT result {result}")
        return result

    if request.method == "DELETE":
        rec = request.json.get("rec")
        return airtable.delete_availability(rec)

    return Response(f"Unsupported method {request.method}", status=400)
