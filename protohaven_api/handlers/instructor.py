"""Handlers for instructor actions on classes"""

import datetime
import logging
from collections import defaultdict
from typing import Any, Optional, Union

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, redirect, request

from protohaven_api.automation.classes import scheduler
from protohaven_api.automation.classes import validation as val
from protohaven_api.config import get_config, safe_parse_datetime, tznow
from protohaven_api.handlers.auth import user_email, user_fullname
from protohaven_api.integrations import airtable, airtable_base, comms, neon, neon_base
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


def get_instructor_readiness(inst: list, caps: Optional[Any] = None) -> dict:
    """Returns a list of actions instructors need to take to be fully onboarded.
    Note: `inst` is a neon result requiring Account Current Membership Status"""
    result = {
        "neon_id": None,
        "email_status": "OK",
        "email": None,
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
        result["email_status"] = f"{len(inst)} duplicate accounts in Neon"
    inst_member = inst[0]  # Get the first member from the list

    log.info(str(inst_member))
    result["email"] = inst_member.email
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
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
def instructor_class_templates():
    """Used in scheduling V2 to fetch instructor-relevant details about specific class templates"""
    ids = set(request.args.get("ids").split(","))
    if len(ids) == 0:
        return Response("Requires URL parameter 'ids'", status=400)
    result = {}
    for c in airtable.get_all_class_templates(raw=False):
        if str(c.class_id) in ids and c.approved and c.schedulable:
            result[c.class_id] = c.as_response()
    return result


@page.route("/instructor/class/attendees")
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
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


def get_dashboard_schedule_sorted(email, now=None) -> list[airtable.ScheduledClass]:
    """Fetches the class schedule for an individual instructor.
    Excludes unconfirmed classes sooner than HIDE_UNCONFIRMED_DAYS_AHEAD
    as well as confirmed classes older than HIDE_CONFIRMED_DAYS_AFTER"""
    sched = []
    if now is None:
        now = tznow()
    age_out_thresh = now - datetime.timedelta(days=HIDE_CONFIRMED_DAYS_AFTER)
    confirmation_thresh = now + datetime.timedelta(days=HIDE_UNCONFIRMED_DAYS_AHEAD)
    for s in airtable.get_class_automation_schedule(raw=False):
        if s.instructor_email != email or s.rejected:
            continue
        if s.confirmed and s.end_time <= age_out_thresh:
            continue
        if not s.confirmed and s.start_time <= confirmation_thresh:
            continue
        sched.append(s)

    sched.sort(key=lambda s: s.start_time)
    return sched


@page.route("/instructor/about")
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
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
    inst = list(
        neon.search_members_by_email(
            email.lower(), fields=neon.MEMBER_SEARCH_OUTPUT_FIELDS + ["Email 1"]
        )
    )
    if len(inst) == 0:
        return Response(
            f"Instructor data not found for email {email.lower()}", status=404
        )
    return get_instructor_readiness(inst)


@page.route("/instructor")
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
def instructor_class():
    """Return svelte compiled static page for instructor dashboard"""
    return current_app.send_static_file("svelte/instructor.html")


@page.route("/instructor/_app/immutable/<typ>/<path>")
def instructor_class_svelte_files(typ, path):
    """Return svelte compiled static page for instructor dashboard"""
    return current_app.send_static_file(f"svelte/_app/immutable/{typ}/{path}")


@page.route("/instructor/class_details")
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
def instructor_class_details():
    """Display all class information about a particular instructor (via email)"""
    email, rep = _resolve_email()
    if rep:
        return rep

    email = email.lower()
    sched = get_dashboard_schedule_sorted(email)

    # Look up the name on file in the capabilities list - this is used to match
    # on manually entered calendar availability
    caps_name = {v: k for k, v in airtable.get_instructor_email_map().items()}.get(
        email, "<NOT FOUND>"
    )

    return {
        "schedule": [c.as_response() for c in sched],
        "now": tznow(),
        "email": email,
        "name": caps_name,
    }


@page.route("/instructor/class/update", methods=["POST"])
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
def instructor_class_update():
    """Confirm or unconfirm a class to run, by the instructor"""
    data = request.json
    eid = data["eid"]
    pub = data["pub"]
    result = airtable.respond_class_automation_schedule(eid, pub)
    return result.as_response()


@page.route("/instructor/class/supply_req", methods=["POST"])
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
def instructor_class_supply_req():
    """Mark supplies as missing or confirmed for a class"""
    data = request.json
    eid = data["eid"]
    c = airtable.get_scheduled_class(eid, raw=False)
    if not c:
        raise RuntimeError(f"Not found: class {eid}")

    state = "Supplies Requested" if data["missing"] else "Supplies Confirmed"
    result = airtable.mark_schedule_supply_request(eid, state)

    comms.send_discord_message(
        f"{user_fullname()} set {state} for "
        f"{c.name} with {c.instructor_name} "
        f"on {c.start_time.strftime('%Y-%m-%d %-I:%M %p')}",
        "#supply-automation",
        blocking=False,
    )
    return result.as_response()


@page.route("/instructor/class/volunteer", methods=["POST"])
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
def instructor_class_volunteer():
    """Change the volunteer state of a class"""
    data = request.json
    eid = data["eid"]
    v = data["volunteer"]
    return airtable.mark_schedule_volunteer(eid, v).as_response()


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
                "period": fields.get("Period"),
                "name (from area)": fields.get("Name (from Area)"),
                "image link": fields.get("Image Link"),
            }
        )
    return dict(result)


def _resolve_class_proposal_params():
    data = request.json
    if "cls_id" not in data:
        return (
            None,
            None,
            None,
            Response("`cls_id` required in JSON body", status=400),
            False,
        )
    cls_id = str(data["cls_id"])
    if "sessions" not in data:
        return (
            None,
            None,
            None,
            Response("`sessions` required in JSON body", status=400),
            False,
        )
    sessions: list[val.Interval] = []
    for s in data["sessions"]:
        log.info(f"Parsing session {s}")
        sessions.append(tuple(safe_parse_datetime(t) for t in s))
    inst_id, rep = _resolve_email()

    skip_val = data.get("skip_validation") or False
    if not isinstance(skip_val, bool):  # Strict checks on validation override
        skip_val = False
    log.info(f"skip_val: {skip_val}")
    if skip_val and not am_role(Role.ADMIN, Role.EDUCATION_LEAD, Role.STAFF):
        return (
            None,
            None,
            None,
            Response("`skip_validation` permission denied", status=400),
            False,
        )

    return cls_id, sessions, inst_id, rep, data.get("skip_validation") or False


@page.route("/instructor/validate", methods=["POST"])
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
def validate_class():
    """Validates the instructor's selected class and session times, returning
    a list of error messages if anything fails validation"""
    cls_id, sessions, inst_id, rep, _ = _resolve_class_proposal_params()
    if rep:
        return rep
    log.info(f"Validating instructor {inst_id} class schedule for {cls_id}: {sessions}")
    errors = scheduler.validate(inst_id, cls_id, sessions)
    log.info(f"Result: {errors}")
    return {"valid": len(errors) == 0, "errors": errors}


@page.route("/instructor/push_class", methods=["POST"])
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
def push_class():
    """Push specific classes to airtable, after running validation checks one last time."""
    cls_id, sessions, inst_id, rep, skip_validation = _resolve_class_proposal_params()
    if rep:
        return rep

    if not skip_validation:
        log.info(
            f"Validating instructor {inst_id} class schedule for {cls_id}: {sessions}"
        )
        errors = scheduler.validate(inst_id, cls_id, sessions)
        log.info(f"Result: {errors}")
        if len(errors) > 0:
            return {"valid": len(errors) == 0, "errors": errors}

    # We automatically confirm classes pushed via instructor dashboard since the instructor
    # is the one pushing the class.
    scheduler.push_class_to_schedule(inst_id, cls_id, sessions)
    return {"valid": True, "errors": [], "success": True}


@page.route("/instructor/class/neon_state", methods=["GET"])
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
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
@require_login_role(Role.INSTRUCTOR, Role.EDUCATION_LEAD, Role.STAFF)
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
