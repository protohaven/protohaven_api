from flask import Blueprint, render_template, request

from integrations import discord_bot, neon
from rbac import Role, require_login_role

page = Blueprint("tech_lead", __name__, template_folder="templates")


@page.route("/tech_lead/techs_clearances")
@require_login_role(Role.SHOP_TECH_LEAD)
def techs_clearances():
    techs = []
    for t in neon.getMembersWithRole(
        Role.SHOP_TECH, [neon.CUSTOM_FIELD_CLEARANCES, neon.CUSTOM_FIELD_INTEREST]
    ):
        clr = []
        if t.get("Clearances") is not None:
            clr = t["Clearances"].split("|")
        interest = t.get("Interest", "")
        techs.append(
            dict(
                id=t["Account ID"],
                name=f"{t['First Name']} {t['Last Name']}",
                interest=interest,
                clearances=clr,
            )
        )
    techs.sort(key=lambda t: len(t["clearances"]))
    return render_template("techs_clearances.html", techs=techs)
