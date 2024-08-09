"""Site for tech leads to manage shop techs"""
import logging
from collections import defaultdict

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, redirect, request

from protohaven_api.config import tz, tznow
from protohaven_api.forecasting import techs as forecast
from protohaven_api.integrations import airtable, neon
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


def _fetch_tool_states_and_areas(now):
    tool_states = defaultdict(list)
    now = now.astimezone(tz)
    areas = set()  # aggregated from tool list so it only shows areas with tools
    for t in airtable.get_tools():
        # Collect areas, excluding a few that don't need leads
        area = t["fields"].get("Name (from Shop Area)")
        if area and area[0].strip() not in (
            "Back Yard",
            "Kitchen",
            "Digital",
            "Design Hub",
            "Hand Tools",
            "Staff Room",
            "Maintenance",
            "Conference Room",
            "Design Classroom",
        ):
            areas.add(area[0].strip())
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
    for t in techs:
        if not t.get("area_lead"):
            continue
        for a in t.get("area_lead").split(","):
            a = a.strip()
            if a not in area_map:
                log.warning(f"Tech {t['name']} is area lead of invalid area {a}")
            else:
                area_map[a].append(t["name"])
    return area_map


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


@page.route("/techs/forecast/override", methods=["POST", "DELETE"])
@require_login_role(Role.SHOP_TECH)
def techs_forecast_override():
    """Update/remove forecast overrides on shop tech forecast"""
    data = request.json
    if request.method == "POST":
        status, content = airtable.set_forecast_override(
            data.get("id"),
            data["date"],
            data["ap"],
            data["techs"],
            data.get("email"),
            data.get("fullname"),
        )
        if status != 200:
            return Response(content, status=status)
        return content
    if request.method == "DELETE":
        return airtable.delete_forecast_override(data["id"])

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
