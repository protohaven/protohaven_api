"""Site for tech leads to manage shop techs"""

import datetime
import logging
from collections import defaultdict

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, redirect, request, session

from protohaven_api.automation.techs import techs as forecast
from protohaven_api.config import tz, tznow
from protohaven_api.integrations import airtable, comms, neon, neon_base
from protohaven_api.rbac import Role, get_roles
from protohaven_api.rbac import is_enabled as is_rbac_enabled
from protohaven_api.rbac import require_login_role

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
    tool_states = defaultdict(list)
    now = now.astimezone(tz)
    areas = {
        a["fields"]["Name"].strip()
        for a in airtable.get_areas()
        if a["fields"]["Name"] not in EXCLUDED_AREAS
    }
    for t in airtable.get_tools():
        status = t["fields"].get("Current Status", "Unknown")
        msg = t["fields"].get("Status Message", "Unknown")
        modified = t["fields"].get("Status last modified")
        if modified:
            modified = (now - dateparser.parse(modified)).days
        else:
            modified = 0
        date = t["fields"].get("Status last modified", "")
        if date != "":
            date = dateparser.parse(date).strftime("%Y-%m-%d")
        tool_states[status].append(
            {
                "name": t["fields"]["Tool Name"],
                "code": t["fields"]["Tool Code"],
                "modified": modified,
                "message": msg,
                "date": date,
            }
        )
    for _, vv in tool_states.items():
        vv.sort(key=lambda k: k["modified"], reverse=True)
    return tool_states, areas


@page.route("/techs/tool_state")
def techs_tool_state():
    """Fetches info on current state of tools"""
    tool_states, _ = _fetch_tool_states_and_areas(tznow())
    return tool_states


@page.route("/techs/shifts")
def techs_shifts():
    """Fetches shift information for all techs"""
    return forecast.get_shift_map()


@page.route("/techs/area_leads")
def techs_area_leads():
    """Fetches the mapping of areas to area leads"""
    _, areas = _fetch_tool_states_and_areas(tznow())
    techs = neon.fetch_techs_list()
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
    return forecast.generate(date, forecast_len)


def _notify_override(name, shift, techs):
    """Sends notification of state of class to the techs and instructors channels
    when a tech (un)registers to backfill a class."""
    msg = (
        f"**On duty for {shift}**: {', '.join(techs)} (edited by {name})"
        "\n*Make additional changes to the shift schedule "
        "[here](https://api.protohaven.org/techs#cal) (requires login)*"
    )
    comms.send_discord_message(msg, "#techs", blocking=False)


@page.route("/techs/forecast/override", methods=["POST", "DELETE"])
@require_login_role(Role.SHOP_TECH)
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
    techs = neon.fetch_techs_list()
    roles = get_roles()
    tech_lead = (not is_rbac_enabled()) or (
        roles is not None and Role.SHOP_TECH_LEAD["name"] in roles
    )
    return {
        "tech_lead": tech_lead,
        "techs": techs,
    }


@page.route("/techs/update", methods=["POST"])
@require_login_role(Role.SHOP_TECH_LEAD)
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


@page.route("/techs/enroll", methods=["POST"])
@require_login_role(Role.SHOP_TECH_LEAD)
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
    log.info(f"Fetched {len(supply_cost_map)} class supply costs")
    for_techs = []
    now = tznow()
    # Should dedupe logic with builder.py eventually
    for evt in neon.fetch_upcoming_events():
        if str(evt["id"]) == "17631":  # Private instruction
            continue
        start = dateparser.parse(evt["startDate"] + " " + evt["startTime"]).astimezone(
            tz
        )
        if start - datetime.timedelta(days=1) > now or now > start:
            continue
        attendees = {
            a["accountId"]
            for a in neon.fetch_attendees(evt["id"])
            if a["registrationStatus"] == "SUCCEEDED"
        }

        if len(attendees) < evt["capacity"]:
            tid = None
            for t in neon.fetch_tickets(evt["id"]):
                tid = t["id"]
                if t["name"] == "Single Registration":
                    log.info(f"Found single registration ticket id {tid}")
                    break
            if not tid:
                raise RuntimeError(
                    f"Failed to get ticket IDs from event {evt['id']} for registration"
                )

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
    return for_techs


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
    action = "registered for" if action == "register" else "unregistered from"
    msg = (
        f"{acc.get('firstName')} {acc.get('lastName')} {action} "
        f"{evt.get('name')} on {evt.get('startDate')}"
        f"; {evt.get('capacity', 0) - len(attendees)} seat(s) remain"
    )
    comms.send_discord_message(msg, "#instructors", blocking=False)
    msg += (
        "\n\n*Make registration changes [here](https://api.protohaven.org/techs#events "
        "(login required)"
    )
    comms.send_discord_message(msg, "#techs", blocking=False)


@page.route("/techs/event", methods=["POST"])
@require_login_role(Role.SHOP_TECH)
def techs_event_registration():
    """Enroll a Neon account in the shop tech program, via email"""
    account_id = session["neon_id"]
    data = request.json
    event_id = data.get("event_id")
    ticket_id = data.get("ticket_id")
    action = data.get("action")
    if not account_id:
        return Response("Not logged in", status=401)
    if not event_id or not ticket_id or not action in ("register", "unregister"):
        return Response("Invalid argument", status=400)

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
