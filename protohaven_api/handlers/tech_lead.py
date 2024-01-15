"""Site for tech leads to manage shop techs"""
from flask import Blueprint, render_template

from protohaven_api.integrations import neon
from protohaven_api.rbac import Role, require_login_role

page = Blueprint("tech_lead", __name__, template_folder="templates")


@page.route("/tech_lead/techs_clearances")
@require_login_role(Role.SHOP_TECH_LEAD)
def techs_clearances():
    """Show organized list of techs, clearances, and interest in tools"""
    techs = []
    for t in neon.get_members_with_role(
        Role.SHOP_TECH, [neon.CUSTOM_FIELD_CLEARANCES, neon.CUSTOM_FIELD_INTEREST]
    ):
        clr = []
        if t.get("Clearances") is not None:
            clr = t["Clearances"].split("|")
        interest = t.get("Interest", "")
        techs.append(
            {
                "id": t["Account ID"],
                "name": f"{t['First Name']} {t['Last Name']}",
                "interest": interest,
                "clearances": clr,
            }
        )
    techs.sort(key=lambda t: len(t["clearances"]))
    return render_template("techs_clearances.html", techs=techs)
