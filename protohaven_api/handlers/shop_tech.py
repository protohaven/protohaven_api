"""Web pages for shop techs"""
from flask import Blueprint, render_template, request, session

from protohaven_api.integrations import neon, wiki
from protohaven_api.rbac import Role, require_login_role

page = Blueprint("shop_tech", __name__, template_folder="templates")


@page.route("/shop_tech/handoff")
@require_login_role(Role.SHOP_TECH)
def shop_tech_handoff():
    """Form for submitting handoff reports at the end of a shift"""
    shift_tasks = wiki.get_shop_tech_shift_tasks()
    return render_template("shop_tech_handoff.html", shift_tasks=shift_tasks)


@page.route("/shop_tech/profile", methods=["GET", "POST"])
@require_login_role(Role.SHOP_TECH)
def shop_tech_profile():
    """Editable profile for shop tech specific information"""
    user = session["neon_id"]
    if request.method == "POST":
        interest = request.form["interest"]
        neon.set_interest(user, interest)
        session["neon_account"] = neon.fetch_account(session["neon_id"])

    interest = ""
    for cf in session["neon_account"]["individualAccount"]["accountCustomFields"]:
        if cf["name"] == "Interest":
            interest = cf["value"]
            break
    return render_template("shop_tech_profile.html", interest=interest)
