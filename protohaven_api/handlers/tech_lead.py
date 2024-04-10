"""Site for tech leads to manage shop techs"""
import datetime
from collections import defaultdict

from dateutil import parser as dateparser
from flask import Blueprint, request

from protohaven_api.config import tz
from protohaven_api.integrations import airtable, neon
from protohaven_api.rbac import Role, require_login_role

page = Blueprint("tech_lead", __name__, template_folder="templates")


def _fetch_techs_list():
    techs = []
    for t in neon.get_members_with_role(
        Role.SHOP_TECH,
        [
            "Email 1",
            neon.CUSTOM_FIELD_CLEARANCES,
            neon.CUSTOM_FIELD_INTEREST,
            neon.CUSTOM_FIELD_EXPERTISE,
            neon.CUSTOM_FIELD_AREA_LEAD,
            neon.CUSTOM_FIELD_SHOP_TECH_SHIFT,
        ],
    ):
        clr = []
        if t.get("Clearances") is not None:
            clr = t["Clearances"].split("|")
        interest = t.get("Interest", "")
        expertise = t.get("Expertise", "")
        area_lead = t.get("Area Lead", "")
        shift = t.get("Shop Tech Shift", "")
        print(t)
        techs.append(
            {
                "id": t["Account ID"],
                "name": f"{t['First Name']} {t['Last Name']}",
                "email": t["Email 1"],
                "interest": interest,
                "expertise": expertise,
                "area_lead": area_lead,
                "shift": shift,
                "clearances": clr,
            }
        )
    techs.sort(key=lambda t: len(t["clearances"]))
    return techs


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
        print(t["fields"])
        modified = t["fields"].get("Status last modified")
        if modified:
            modified = (now - dateparser.parse(modified)).days
        else:
            modified = 0
        tool_states[status].append(
            {
                "modified": modified,
                "name": t["fields"]["Tool Name"],
            }
        )
    for k, vv in tool_states.items():
        vv.sort(key=lambda k: k["modified"], reverse=True)
    tool_states = {k: v[:10] for k, v in tool_states.items()}  # Truncate for display
    return tool_states, areas


@page.route("/tech_lead/all_status")
def tech_lead_all_status():
    """Fetches shift info, tech info, all the info!"""
    techs = _fetch_techs_list()

    now = datetime.datetime.now().replace(
        hour=0, minute=0, second=0
    ) - datetime.timedelta(days=1)
    time_off = [
        t
        for t in airtable.get_shop_tech_time_off()
        if dateparser.parse(t["fields"]["Date"]) >= now
    ]
    time_off.sort(key=lambda t: dateparser.parse(t["fields"]["Date"]))

    tool_states, areas = _fetch_tool_states_and_areas(now)
    return {
        "techs": techs,
        "time_off": time_off,
        "tool_states": tool_states,
        "areas": list(areas),
    }


@page.route("/tech_lead/update", methods=["POST"])
@require_login_role(Role.SHOP_TECH_LEAD)
def tech_update():
    """Update the custom fields of a shop tech in Neon"""
    data = request.json
    nid = data["id"]
    body = {
        k: v
        for k, v in data.items()
        if k in ("shift", "area_lead", "interest", "expertise")
    }
    rep, content = neon.set_tech_custom_fields(nid, **body)
    assert rep.status == 200
    return content


@page.route("/tech_lead/enroll", methods=["POST"])
@require_login_role(Role.SHOP_TECH_LEAD)
def tech_lead_enroll():
    """Enroll a Neon account in the shop tech program, via email"""
    data = request.json
    resp, _ = neon.patch_member_role(data["email"], Role.SHOP_TECH, data["enroll"])
    assert resp.status == 200
    return "ok"
