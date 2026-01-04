"""Handlers for instructor actions on classes"""

import datetime
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, redirect, request

from protohaven_api.automation.classes import scheduler
from protohaven_api.automation.classes import validation as val
from protohaven_api.config import ParserError, get_config, safe_parse_datetime, tznow
from protohaven_api.handlers.auth import user_email, user_fullname
from protohaven_api.integrations import (
    airtable,
    airtable_base,
    booked,
    comms,
    neon,
    neon_base,
)
from protohaven_api.integrations.models import Role
from protohaven_api.rbac import am_role, require_login_role

log = logging.getLogger("handlers.instructor")

page = Blueprint("instructor", __name__, template_folder="templates")


# UI display constants from config
HIDE_UNCONFIRMED_DAYS_AHEAD = get_config(
    "general/ui_constants/hide_unconfirmed_days_ahead", 10
)
HIDE_CONFIRMED_DAYS_AFTER = get_config(
    "general/ui_constants/hide_confirmed_days_after", 10
)


def prefill_form(  # pylint: disable=too-many-locals, too-many-arguments
    instructor: str,
    start_date: datetime.datetime,
    hours: float,
    class_name: str,
    pass_emails: List[str],
    clearances: List[str],
    volunteer: bool,
    event_id: str,
) -> str:
    """Return prefilled instructor log submission form"""
    individual = airtable.get_instructor_log_tool_codes()
    clearance_codes = []
    tool_codes = []
    for c in clearances:
        if c in individual:
            tool_codes.append(c)
        else:
            clearance_codes.append(c)

    # Get form configuration
    form_base = get_config("forms/instructor_log/base_url")
    form_keys = get_config("forms/instructor_log/keys")
    form_values = get_config("forms/instructor_log/values")

    start_yyyy_mm_dd = start_date.strftime("%Y-%m-%d")
    result = f"{form_base}?usp=pp_url"
    result += f"&{form_keys['instructor']}={instructor}"
    result += f"&{form_keys['date']}={start_yyyy_mm_dd}"
    result += f"&{form_keys['hours']}={hours}"
    result += f"&{form_keys['class_name']}={class_name}"
    if volunteer:
        result += f"&{form_keys['volunteer']}={form_values['volunteer_yes']}"
    result += f"&{form_keys['session_type']}={form_values['single_session']}"
    result += f"&{form_keys['pass_emails']}={', '.join(pass_emails)}"
    for cc in clearance_codes:
        result += f"&{form_keys['clearance_codes']}={cc}"
    tool_usage_value = (
        form_values["tool_usage_yes"]
        if len(tool_codes) > 0
        else form_values["tool_usage_no"]
    )
    result += f"&{form_keys['tool_usage']}={tool_usage_value}"
    result += f"&{form_keys['event_id']}={event_id}"
    for tc in tool_codes:
        result += f"&{form_keys['tool_codes']}={tc}"
    return result


def get_instructor_readiness(inst: list, caps: Optional[Any] = None) -> dict:
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
    inst_member = inst[0]  # Get the first member from the list

    result["neon_id"] = inst_member.neon_id
    if inst_member.account_current_membership_status == "Active":
        result["active_membership"] = "OK"
    else:
        result["active_membership"] = inst_member.account_current_membership_status
    if inst_member.discord_user:
        result["discord_user"] = "OK"
    result["fullname"] = f"{inst_member.fname} {inst_member.lname}"
    if not caps:
        caps = airtable.fetch_instructor_capabilities(result["fullname"])
    if caps:
        result["airtable_id"] = caps["id"]
        if len(caps["classes"]) > 0:
            result["capabilities_listed"] = "OK"
        result["classes"] = caps["classes"]
        missing_info = [
            x
            for x in [
                "W9" if not caps["w9"] else None,
                ("Direct Deposit" if not caps["direct_deposit"] else None),
                "Profile Pic" if not caps["profile_pic"] else None,
                "Bio" if not caps["bio"] else None,
            ]
            if x
        ]
        result["profile_img"] = caps["profile_pic"]
        result["bio"] = caps["bio"]
        if len(missing_info) > 0:
            result["paperwork"] = f"Missing {', '.join(missing_info)}"
        else:
            result["paperwork"] = "OK"

    return result


def _resolve_email():
    email = request.args.get("email")
    if email is not None:
        ue = user_email()
        if ue != email and not am_role(Role.ADMIN, Role.EDUCATION_LEAD, Role.STAFF):
            return None, Response(
                "Access Denied for admin parameter `email`", status=401
            )
    else:
        email = user_email()
        if not email:
            return None, Response("You are not logged in.", status=401)
    return email, None


@page.route("/instructor/class/templates")
@require_login_role(Role.INSTRUCTOR)
def instructor_class_templates():
    """Used in scheduling V2 to fetch instructor-relevant details about specific class templates"""
    ids = set(request.args.get("ids").split(","))
    if len(ids) == 0:
        return Response("Requires URL parameter 'ids'", status=400)
    result = {}
    for row in airtable.get_all_class_templates():
        f = row["fields"]
        rid = str(row["id"])
        if rid in ids and f.get("Approved") and f.get("Schedulable"):
            result[rid] = {
                "capacity": f.get("Capacity"),
                "days": f.get("Days"),
                "hours": f.get("Hours"),
                "price": f.get("Price"),
                "clearances": f.get("Form Name (from Clearance)"),
            }
    return result


@page.route("/instructor/class/attendees")
@require_login_role(Role.INSTRUCTOR)
def instructor_class_attendees() -> Union[Response, str]:
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
                m = neon_base.fetch_account(a["accountId"])
                if m is not None:
                    a["email"] = m.email
            except RuntimeError:
                pass

    return result


@page.route("/instructor/class")
def instructor_class_selector_redirect1() -> Any:
    """Used previously. This redirects to the new endpoint"""
    return redirect("/instructor")


@page.route("/instructor/class_selector")
def instructor_class_selector_redirect2() -> Any:
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

        start_date = safe_parse_datetime(s["fields"]["Start Time"])
        dates = list(
            expand_recurrence(
                (s["fields"].get("Recurrence (from Class)") or [None])[0],
                (s["fields"].get("Hours (from Class)") or [0])[0],
                start_date,
            )
        )
        end_date = dates[-1][0]
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
        if ue != email and not am_role(Role.ADMIN, Role.EDUCATION_LEAD, Role.STAFF):
            return Response("Access Denied for admin parameter `email`", status=401)
    else:
        email = user_email()
        if not email:
            return Response("You are not logged in.", status=401)
    inst = list(neon.search_members_by_email(email.lower()))
    if len(inst) == 0:
        return Response(
            f"Instructor data not found for email {email.lower()}", status=404
        )
    return get_instructor_readiness(inst)


def _annotate_schedule_class(e):
    date = safe_parse_datetime(e["Start Time"])

    # If it's in neon, generate a log URL.
    # Placeholder for attendee names/emails as that's loaded
    # lazily on page load.
    if e.get("Neon ID"):
        e["prefill"] = prefill_form(
            instructor=e.get("Instructor") or "UNKNOWN",
            start_date=date,
            hours=(e.get("Hours (from Class)") or [0])[0],
            class_name=(e.get("Name (from Class)") or ["UNKNOWN"])[0],
            pass_emails=["$ATTENDEE_NAMES"],
            clearances=e.get("Form Name (from Clearance) (from Class)", ["n/a"]),
            volunteer=e.get("Volunteer", False),
            event_id=e.get("Neon ID") or "UNKNOWN",
        )

    for date_field in ("Confirmed", "Instructor Log Date"):
        if e.get(date_field):
            e[date_field] = safe_parse_datetime(e[date_field])
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
        if ue != email and not am_role(Role.ADMIN, Role.EDUCATION_LEAD, Role.STAFF):
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
    status, result = airtable.respond_class_automation_schedule(eid, pub)
    if status != 200:
        raise RuntimeError(result)
    return _annotate_schedule_class(result["fields"])


@page.route("/instructor/class/supply_req", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_supply_req():
    """Mark supplies as missing or confirmed for a class"""
    data = request.json
    eid = data["eid"]
    c = airtable.get_scheduled_class(eid)
    if not c:
        raise RuntimeError(f"Not found: class {eid}")

    state = "Supplies Requested" if data["missing"] else "Supplies Confirmed"
    status, result = airtable.mark_schedule_supply_request(eid, state)
    if status != 200:
        raise RuntimeError(f"Error setting supply state: {result}")

    d = safe_parse_datetime(c["fields"]["Start Time"])
    comms.send_discord_message(
        f"{user_fullname()} set {state} for "
        f"{', '.join(c['fields']['Name (from Class)'])} with {c['fields']['Instructor']} "
        f"on {d.strftime('%Y-%m-%d %-I:%M %p')}",
        "#supply-automation",
        blocking=False,
    )
    return _annotate_schedule_class(result["fields"])


@page.route("/instructor/class/volunteer", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_volunteer():
    """Change the volunteer state of a class"""
    data = request.json
    eid = data["eid"]
    v = data["volunteer"]
    status, result = airtable.mark_schedule_volunteer(eid, v)
    if status != 200:
        raise RuntimeError(result)
    return _annotate_schedule_class(result["fields"])


@page.route("/instructor/admin_data", methods=["GET"])
@require_login_role(Role.EDUCATION_LEAD, Role.BOARD_MEMBER, Role.STAFF)
def admin_data():
    """Fetches and returns admin info for Edu Leads and other privileged roles"""
    result = defaultdict(list)
    for inst in airtable_base.get_all_records("class_automation", "capabilities"):
        result["capabilities"].append(
            {
                "name": inst["fields"].get("Instructor") or "unknown",
                "email": inst["fields"].get("Email") or "unknown",
                "active": inst["fields"].get("Active") or False,
            }
        )
    for tmpl in airtable_base.get_all_records("class_automation", "classes"):
        fields = tmpl.get("fields") or {}
        result["classes"].append(
            {
                "name": fields.get("Name"),
                "approved": fields.get("Approved"),
                "schedulable": fields.get("Schedulable"),
                "clearances earned": fields.get("Clearances Earned"),
                "age requirement": fields.get("Age Requirement"),
                "capacity": fields.get("Capacity"),
                "supply_cost": fields.get("Supply Cost"),
                "price": fields.get("Price"),
                "hours": fields.get("Hours"),
                "recurrence": fields.get("Recurrence"),
                "period": fields.get("Period"),
                "name (from area)": fields.get("Name (from Area)"),
                "image link": fields.get("Image Link"),
            }
        )
    return dict(result)


@page.route("/instructor/validate", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def validate_class():
    """Validates the instructor's selected class and session times, returning
    a list of error messages if anything fails validation"""
    data = request.json
    if "cls_id" not in data:
        return Response("`cls_id` required in JSON body", status=400)
    cls_id = str(data["cls_id"])
    if "sessions" not in data:
        return Response("`sessions` required in JSON body", status=400)
    sessions: list[val.Interval] = []
    for s in data["sessions"]:
        log.info(f"Parsing session {s}")
        sessions.append(tuple(safe_parse_datetime(t) for t in s))
    inst_id, rep = _resolve_email()
    if rep:
        return rep
    log.info(f"Validating instructor {inst_id} class schedule for {cls_id}: {sessions}")
    errors = scheduler.validate(inst_id, cls_id, sessions)
    log.info(f"Result: {errors}")
    return {"valid": len(errors) == 0, "errors": errors}


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

    raise Exception("TODO parse the data per validate_class")

    fullname = list(data.keys())[0]
    ufn = user_fullname()
    if ufn != fullname and require_login_role(Role.ADMIN)(lambda: True)() is not True:
        return Response(
            f"Access Denied for pushing classes for instructor '{fullname}'", status=401
        )

    # We automatically confirm classes pushed via instructor dashboard since the instructor
    # is the one pushing the class.
    scheduler.push_schedule(data, autoconfirm=True)
    return {"success": True}


@page.route("/instructor/class/neon_state", methods=["GET"])
@require_login_role(Role.INSTRUCTOR)
def class_neon_state():
    """Fetch the current state of the class in Neon"""
    event_id = request.args.get("id")
    if event_id is None:
        return Response("Requires URL parameter 'id'", status=400)
    evt = neon.fetch_event(event_id)
    return {
        "publishEvent": evt.published,
        "archived": evt.archived,
    }


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


def _get_availability(inst, t0, t1):
    """We parallelize data fetching here to reduce the load time for
    instructor dashboard calendar edits"""
    with ThreadPoolExecutor() as executor:
        avail_future = executor.submit(airtable.get_instructor_availability, inst)
        sched_future = executor.submit(airtable.get_class_automation_schedule)
        res_future = executor.submit(booked.get_reservations, t0, t1)

        avail = list(avail_future.result())
        sched_raw = list(sched_future.result())
        res_raw = list(res_future.result().get("reservations", []))

    expanded = list(airtable.expand_instructor_availability(avail, t0, t1))
    sched = [
        s
        for s in sched_raw
        if safe_parse_datetime(s["fields"]["Start Time"]) >= t0
        and not s["fields"].get("Rejected")
    ]
    reservations = [
        (
            res["bufferedStartDate"],
            res["bufferedEndDate"],
            res["resourceName"],
            f"{res['firstName']} {res['lastName']}",
            f"https://reserve.protohaven.org/Web/reservation/?rn={res['referenceNumber']}",
        )
        for res in res_raw
    ]
    return {
        "records": {r["id"]: r["fields"] for r in avail},
        "availability": expanded,
        "schedule": sched,
        "reservations": reservations,
    }


@page.route("/instructor/calendar/availability", methods=["GET", "PUT", "DELETE"])
def inst_availability():  # pylint: disable=too-many-return-statements
    """Different methods for CRUD actions on Availability records in airtable, used to
    describe an instructor's availability"""
    if request.method == "GET":
        inst = request.values.get("inst").lower()
        try:
            t0 = safe_parse_datetime(request.values["t0"])
            t1 = safe_parse_datetime(request.values["t1"])
        except (ParserError, TypeError):
            return Response(
                "Both t0 and t1 required in request to /instructor/calendar/availability",
                status=400,
            )
        t1 += datetime.timedelta(
            hours=get_config("general/ui_constants/hours_in_day", 24)
        )  # End date is inclusive
        return _get_availability(inst, t0, t1)

    if request.method == "PUT":
        rec = request.json.get("rec")
        try:
            inst_id = request.json["inst_id"]
            t0 = safe_parse_datetime(request.json["t0"])
            t1 = safe_parse_datetime(request.json["t1"])
        except (ParserError, TypeError, KeyError):
            return Response(
                "t0, t1, inst_id required in json PUT to /instructor/calendar/availability",
                status=400,
            )
        if t0 > t1:
            return Response(
                f"Start (t0) must be before End (t1) - got t0={t0}, t1={t1}",
                status=400,
            )
        recurrence = request.json.get("recurrence")
        if rec is not None:
            status, result = airtable.update_availability(
                rec, inst_id, t0, t1, recurrence
            )
            assert status == 200
        else:
            status, result = airtable.add_availability(inst_id, t0, t1, recurrence)
            assert status == 200
        log.info(f"PUT result {result}")
        return result

    if request.method == "DELETE":
        rec = request.json.get("rec")
        status, result = airtable.delete_availability(rec)
        assert status == 200
        return {"result": result}

    return Response(f"Unsupported method '{request.method}'", status=400)


@page.route("/instructor/clearance_quiz", methods=["POST"])
@require_login_role(Role.AUTOMATION, Role.INSTRUCTOR)
def log_quiz_submission():
    """Saves the results of a clearance quiz in the Quiz Results airtable

    https://wiki.protohaven.org/books/drafts/page/how-to-create-a-recertification-clearance-quiz
    """
    req = request.json
    log.info(f"Clearance quiz received: {req}")
    status, content = airtable.insert_quiz_result(
        submitted=dateparser.parse(req["submitted"]) if "submitted" in req else None,
        email=req.get("email") or None,
        points_to_pass=int(req.get("points_to_pass") or "0"),
        points_scored=int(req.get("points_scored") or "0"),
        tool_codes=req.get("tool_codes") or None,
        data=req.get("data") or {},
    )
    return {"status": status, "content": content}
