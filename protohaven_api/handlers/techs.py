"""Site for tech leads to manage shop techs"""

import datetime
import logging
from collections import defaultdict
from urllib.parse import urljoin

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, redirect, request, session

from protohaven_api.automation.techs import techs as forecast
from protohaven_api.config import tz, tznow
from protohaven_api.integrations import airtable, comms, neon, neon_base, wiki
from protohaven_api.rbac import Role, am_lead_role, am_role, require_login_role

page = Blueprint("techs", __name__, template_folder="templates")


log = logging.getLogger("handlers.techs")


@page.route("/tech_lead")
def techs_selector():
    """Used previously. This redirects to the new endpoint"""
    return redirect("/techs")


@page.route("/techs")
def techs_dash():
    """Return svelte compiled static page for dashboard"""
    return current_app.send_static_file("svelte/techs.html")


@page.route("/_app/immutable/<typ>/<path>")
def techs_dash_svelte_files(typ, path):
    """Return svelte compiled static page for dashboard"""
    return current_app.send_static_file(f"svelte/_app/immutable/{typ}/{path}")


TECH_ONLY_PREFIX = "(SHOP TECH ONLY)"

# Some areas we exclude from results as they are never needed during operations.
EXCLUDED_AREAS = [
    "Back Yard",
    "Kitchen",
    "Digital",
    "Design Hub",
    "Fishbowl",
    "Hand Tools",
    "Staff Room",
    "Maintenance",
    "Conference Room",
    "Design Classroom",
    "Class Supplies",
    "Custodial Room",
    "Rack Storage",
    "Restroom 1",
    "Restroom 2",
]


def _fetch_tool_states_and_areas(now):
    tool_states = []
    now = now.astimezone(tz)
    areas = {
        a["fields"]["Name"].strip()
        for a in airtable.get_areas()
        if a["fields"]["Name"] not in EXCLUDED_AREAS
    }
    for t in airtable.get_tools():
        status = t["fields"].get("Current Status") or "Unknown"
        msg = t["fields"].get("Status Message") or "Unknown"
        modified = t["fields"].get("Status last modified")
        date = modified or ""
        log.info(f"Midified {modified}")
        if modified:
            modified = (now - dateparser.parse(modified).astimezone(tz)).days
            date = dateparser.parse(date).strftime("%Y-%m-%d")
        else:
            modified = 0
        tool_states.append(
            {
                "status": status,
                "name": t["fields"]["Tool Name"],
                "area": t["fields"]["Name (from Shop Area)"],
                "code": t["fields"]["Tool Code"].strip().upper()
                if t["fields"]["Tool Code"]
                else None,
                "modified": modified,
                "message": msg,
                "date": date,
            }
        )
    return tool_states, areas


@page.route("/techs/tool_state")
def techs_tool_state():
    """Fetches info on current state of tools"""
    tool_states, _ = _fetch_tool_states_and_areas(tznow())
    return tool_states


@page.route("/techs/docs_state")
def techs_docs_state():
    """Fetches the state of documentation for all tool pages in the wiki"""
    return wiki.get_tool_docs_summary()


@page.route("/techs/shifts")
def techs_shifts():
    """Fetches shift information for all techs"""
    return forecast.get_shift_map()


@page.route("/techs/members")
@require_login_role(Role.SHOP_TECH, redirect_to_login=False)
def techs_members():
    """Fetches today's sign-in information for members"""
    start = request.values.get("start")
    start = (dateparser.parse(start) if start else tznow()).replace(
        hour=0, minute=0, second=0
    )
    end = start.replace(hour=23, minute=59, second=59)
    log.info(f"Fetching signins from {start} to {end}")
    return list(airtable.get_signins_between(start, end))


@page.route("/techs/area_leads")
def techs_area_leads():
    """Fetches the mapping of areas to area leads"""
    _, areas = _fetch_tool_states_and_areas(tznow())
    techs = neon.fetch_techs_list(include_pii=am_role(Role.SHOP_TECH) or am_lead_role())
    area_map = {a: [] for a in areas}
    extras_map = defaultdict(list)
    for t in techs:
        if not t.get("area_lead"):
            continue
        for a in t.get("area_lead").split(","):
            a = a.strip()
            if a not in area_map:
                extras_map[a].append(t)
            else:
                area_map[a].append(t)
    return {"area_leads": area_map, "other_leads": dict(extras_map)}


DEFAULT_FORECAST_LEN = 14


@page.route("/techs/forecast")
def techs_forecast():
    """Provide advance notice of the level of staffing of tech shifts"""
    date = request.args.get("date")
    if date is None:
        date = tznow()
    else:
        date = dateparser.parse(date).astimezone(tz)
    date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    forecast_len = int(request.args.get("days", DEFAULT_FORECAST_LEN))
    if forecast_len <= 0:
        return Response("Nonzero days required for forecast", status=400)
    return forecast.generate(
        date, forecast_len, include_pii=am_role(Role.SHOP_TECH) or am_lead_role()
    )


def _notify_override(name, shift, techs):
    """Sends notification of state of class to the techs and instructors channels
    when a tech (un)registers to backfill a class."""
    techs = [t.replace("*", "") for t in techs]
    msg = (
        f"**On duty {shift}: {', '.join(techs)}** "
        f"({name} edited via [/techs](https://api.protohaven.org/techs#cal))"
    )
    comms.send_discord_message(msg, "#techs", blocking=False)


@page.route("/techs/forecast/override", methods=["POST", "DELETE"])
@require_login_role(Role.SHOP_TECH, redirect_to_login=False)
def techs_forecast_override():
    """Update/remove forecast overrides on shop tech forecast"""
    data = request.json
    _id = data.get("id")
    fullname = data.get("fullname")
    date = data.get("date")
    ap = data.get("ap")
    techs = data.get("techs")
    orig = data.get("orig")
    if request.method == "POST":
        status, content = airtable.set_forecast_override(
            _id,
            date,
            ap,
            techs,
            data.get("email"),
            fullname,
        )
        if status != 200:
            return Response(content, status=status)
        _notify_override(fullname, f"{date} {ap}", techs)
        return content
    if request.method == "DELETE":
        ret = airtable.delete_forecast_override(data["id"])
        if ret:
            _notify_override(fullname, f"{date} {ap}", orig)
        return ret

    return Response(f"Method {request.method} not supported", status=400)


@page.route("/techs/list")
def techs_list():
    """Fetches tech info and lead status of observer"""
    techs_results = neon.fetch_techs_list(
        include_pii=am_role(Role.SHOP_TECH) or am_lead_role()
    )
    bios_results = airtable.get_all_tech_bios()
    bio_dict = {bio["fields"]["Email"]: bio["fields"] for bio in bios_results}
    for idx, tech in enumerate(techs_results):
        tech_bio = bio_dict.get(tech["email"], {})
        if tech_bio:
            techs_results[idx]["bio"] = tech_bio.get("Bio", "")
            thumbs = tech_bio.get("Picture")[0]["thumbnails"]["large"]
            techs_results[idx]["picture"] = thumbs.get("url") or urljoin(
                "http://localhost:8080",
                thumbs.get("signedPath"),
            )

    return {"tech_lead": am_role(Role.SHOP_TECH_LEAD), "techs": techs_results}


@page.route("/techs/update", methods=["POST"])
@require_login_role(Role.SHOP_TECH_LEAD, redirect_to_login=False)
def tech_update():
    """Update the custom fields of a shop tech in Neon"""
    data = request.json
    nid = data["id"]
    body = {
        k: v
        for k, v in data.items()
        if k in ("shift", "area_lead", "interest", "expertise", "first_day", "last_day")
    }
    return neon.set_tech_custom_fields(nid, **body)


@page.route("/techs/new_event", methods=["POST"])
@require_login_role(
    Role.SHOP_TECH_LEAD, Role.EDUCATION_LEAD, Role.STAFF, redirect_to_login=False
)
def new_tech_event():
    """Create a new techs-only event in Neon"""
    data = request.json
    log.info(f"new_event with data {data}")
    if str(data["name"]).strip() == "":
        log.info("Name field required")
        return Response("name field is required", status=401)
    log.info("Parsing date")
    d = dateparser.parse(data["start"]).astimezone(tz)
    log.info(f"Parsed {d}")
    if not d or d < tznow() or d.hour < 10 or d.hour + data["hours"] > 22:
        return Response(
            "start must be set to a valid date in the future and within business hours (10AM-10PM)",
            status=401,
        )
    log.info("checking capacity")
    if data["capacity"] < 0 or data["capacity"] > 100:
        return Response("capacity field invalid", status=401)
    log.info(f"Creating event with data {data}")
    return neon_base.create_event(
        name=f"{TECH_ONLY_PREFIX} {data['name']}",
        desc="Tech-only event; created via api.protohaven.org/techs dashboard",
        start=d,
        end=d + datetime.timedelta(hours=data["hours"]),
        max_attendees=data["capacity"],
        dry_run=False,
        published=False,  # Do NOT show this in the regular event browser
        registration=True,
        free=True,  # Do not apply pricing
    )


@page.route("/techs/rm_event", methods=["POST"])
@require_login_role(
    Role.SHOP_TECH_LEAD, Role.EDUCATION_LEAD, Role.STAFF, redirect_to_login=False
)
def rm_tech_event():
    """Delete a techs-only event in Neon"""
    data = request.json
    eid = str(data["eid"])
    if eid.strip() == "":
        return Response("eid field required", status=401)
    evt = neon.fetch_event(eid)
    if not evt:
        return Response(f"event with eid {eid} not found", status=404)
    if not evt["name"].startswith(TECH_ONLY_PREFIX):
        return Response(
            f"cannot delete a non-tech-only event missing prefix {TECH_ONLY_PREFIX}",
            status=400,
        )

    return neon.set_event_scheduled_state(evt["id"], scheduled=False)


@page.route("/techs/enroll", methods=["POST"])
@require_login_role(Role.SHOP_TECH_LEAD, redirect_to_login=False)
def techs_enroll():
    """Enroll a Neon account in the shop tech program, via email"""
    data = request.json
    return neon.patch_member_role(data["email"], Role.SHOP_TECH, data["enroll"])


@page.route("/techs/events")
def techs_backfill_events():
    """Returns the list of available events for tech backfill.
    Logic matches automation.classes.builder.Action.FOR_TECHS
    """
    supply_cost_map = {
        str(s["fields"].get("Neon ID", "")): int(
            s["fields"].get("Supply Cost (from Class)", [0])[0]
        )
        for s in airtable.get_class_automation_schedule()
    }
    for_techs = []
    now = tznow()
    # Should dedupe logic with builder.py eventually.
    # We look for unpublished events too since those may be tech events
    for evt in neon.fetch_upcoming_events(published=False):
        if str(evt["id"]) == "17631":  # Private instruction
            continue
        start = dateparser.parse(evt["startDate"] + " " + evt["startTime"]).astimezone(
            tz
        )
        tech_only_event = (
            evt["name"].startswith(TECH_ONLY_PREFIX)
            and evt["enableEventRegistrationForm"]
        )
        tech_backfill_event = (
            evt["publishEvent"]
            and evt["enableEventRegistrationForm"]
            and start - datetime.timedelta(days=1) < now < start
        )

        if not tech_only_event and not tech_backfill_event:
            continue

        attendees = {
            a["accountId"]
            for a in neon.fetch_attendees(evt["id"])
            if a["registrationStatus"] == "SUCCEEDED"
        }

        if tech_only_event or len(attendees) > 0:
            tid = None
            if not tech_only_event:
                # Backfill events are priced; tech-only events are
                # free and have zero ticket IDs
                for t in neon.fetch_tickets(evt["id"]):
                    tid = t["id"]
                    if t["name"] == "Single Registration":
                        log.info(f"Found single registration ticket id {tid}")
                        break
                if not tid:
                    log.warning(
                        f"Failed to get ticket IDs from event {evt['id']} for registration"
                    )
                    # Some events (e.g. All Member Meeting, #18050) lack ticketing information
                    # intentionally as they are free events, but they're not tech-only. In these
                    # cases, we just pretend they don't exist.
                    continue

            for_techs.append(
                {
                    "id": evt["id"],
                    "ticket_id": tid,
                    "name": evt["name"],
                    "attendees": list(attendees),
                    "capacity": evt["capacity"],
                    "start": start,
                    "supply_cost": supply_cost_map.get(str(evt["id"]), 0),
                }
            )

    return {
        "events": for_techs,
        "can_register": am_role(Role.SHOP_TECH) or am_role(Role.SHOP_TECH_LEAD),
        "tech_lead": am_role(Role.SHOP_TECH_LEAD),
    }


def _notify_registration(account_id, event_id, action):
    """Sends notification of state of class to the techs and instructors channels
    when a tech (un)registers to backfill a class."""
    acc, _ = neon_base.fetch_account(account_id, required=True)
    evt = neon.fetch_event(event_id)
    attendees = {
        a["accountId"]
        for a in neon.fetch_attendees(event_id)
        if a["registrationStatus"] == "SUCCEEDED"
    }
    contact = acc.get("primaryContact")
    name = f"{contact.get('firstName')} {contact.get('lastName')}"
    action = "registered for" if action == "register" else "unregistered from"
    msg = (
        f"{name} {action} "
        f"{evt.get('name')} on {evt.get('eventDates').get('startDate')} "
        f"{evt.get('eventDates').get('startTime')}"
        f"; {evt.get('maximumAttendees', 0) - len(attendees)} seat(s) remain"
    )
    # Tech-only classes shouldn't bother instructors
    if not evt.get("name").startswith(TECH_ONLY_PREFIX):
        comms.send_discord_message(msg, "#instructors", blocking=False)
    msg += (
        "\n\n*Make registration changes [here](https://api.protohaven.org/techs#events) "
        "(login required)"
    )
    comms.send_discord_message(msg, "#techs", blocking=False)


@page.route("/techs/event", methods=["POST"])
@require_login_role(Role.SHOP_TECH, redirect_to_login=False)
def techs_event_registration():
    """Enroll a Neon account in the shop tech program, via Neon ID"""
    account_id = session["neon_id"]
    data = request.json
    event_id = data.get("event_id")
    ticket_id = data.get("ticket_id")
    action = data.get("action")
    log.info(f"Attempt to (un)register for event: {account_id} {data}")
    if not account_id:
        return Response("Not logged in", status=401)
    if not event_id:
        return Response("event_id required", status=400)
    if not action in ("register", "unregister"):
        return Response("action must be one of 'register', 'unregister'", status=400)

    if action == "register":
        ret = neon.register_for_event(account_id, event_id, ticket_id)
    else:
        ret = neon.delete_single_ticket_registration(account_id, event_id) or {
            "status": "ok"
        }
    if ret:
        _notify_registration(account_id, event_id, action)
        return ret
    raise RuntimeError("Unknown error handling event registration state")
