"""Site for tech leads to manage shop techs"""
import datetime
import logging
from collections import defaultdict

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, redirect, request

from protohaven_api.config import tz, tznow
from protohaven_api.integrations import airtable, neon
from protohaven_api.rbac import Role, get_roles
from protohaven_api.rbac import is_enabled as is_rbac_enabled
from protohaven_api.rbac import require_login_role

page = Blueprint("techs", __name__, template_folder="templates")

DEFAULT_FORECAST_LEN = 16

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


def _get_shift_map():
    techs = neon.fetch_techs_list()
    shift_map = defaultdict(list)
    for t in techs:
        if not t.get("shift"):
            continue
        for s in t.get("shift").split(","):
            s = s.strip()
            shift_map[s].append(t["name"])
    return dict(shift_map)


@page.route("/techs/shifts")
def techs_shifts():
    """Fetches shift information for all techs"""
    return _get_shift_map()


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


def _calendar_badge_color(num_people):
    """Returns the sveltestrap color tag for a badge given the number of attendant techs"""
    if num_people >= 3:
        return "success"
    if num_people == 2:
        return "info"
    if num_people == 1:
        return "warning"
    return "danger"


def _create_calendar_view(
    start_date, shift_map, shift_term_map, time_off, forecast_len
):  # pylint: disable=too-many-locals
    calendar_view = []
    for i in range(forecast_len):
        day_view = []
        d = start_date + datetime.timedelta(days=i)
        for ap in ["AM", "PM"]:
            s = f"{d.strftime('%A')} {ap}"
            people = shift_map.get(s, [])
            for cov in time_off:
                if (
                    cov["fields"]["Date"] == d.strftime("%Y-%m-%d")
                    and cov["fields"]["Shift"] == ap
                ):
                    people = [
                        p for p in people if p != cov["fields"]["Rendered Shop Tech"]
                    ]
                    if cov["fields"].get("Rendered Covered By"):
                        people.append(cov["fields"]["Rendered Covered By"])

            final_people = []
            for p in people:  # remove if outside of the tech's tenure
                first_day, last_day = shift_term_map.get(p, (None, None))
                if (first_day is None or first_day <= d) and (
                    last_day is None or last_day >= d
                ):
                    final_people.append(p)
            day_view.append(
                {
                    "title": f"{d.strftime('%a %m/%d')} {ap}",
                    "color": _calendar_badge_color(len(people)),
                    "people": final_people,
                    "id": f"Badge{i}{ap}",
                }
            )
        calendar_view.append(day_view)
    return calendar_view


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

    shift_term_map = {
        t["name"]: (
            dateparser.parse(t["first_day"])
            .astimezone(tz)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            if t.get("first_day") is not None
            else None,
            dateparser.parse(t["last_day"])
            .astimezone(tz)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            if t.get("last_day") is not None
            else None,
        )
        for t in neon.fetch_techs_list()
    }
    shift_map = _get_shift_map()

    time_off = [
        t
        for t in airtable.get_shop_tech_time_off()
        if t["fields"].get("Date")
        and dateparser.parse(t["fields"]["Date"]).astimezone(tz) >= date
    ]
    time_off.sort(key=lambda t: dateparser.parse(t["fields"]["Date"]))

    coverage_missing = []
    coverage_ok = []
    for cov in time_off:
        if cov["fields"].get("Covered By", None) is not None:
            coverage_ok.append(cov)
        else:
            coverage_missing.append(cov)

    calendar_view = _create_calendar_view(
        date, shift_map, shift_term_map, time_off, forecast_len
    )
    return {
        "calendar_view": calendar_view,
        "coverage_missing": coverage_missing,
        "coverage_ok": coverage_ok,
    }


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
