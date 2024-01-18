"""Handlers for onboarding steps for new members"""
import time

from flask import Blueprint, redirect, render_template, request

from protohaven_api.integrations import comms, neon
from protohaven_api.rbac import Role, require_login_role

page = Blueprint("onboarding", __name__, template_folder="templates")


@page.route("/onboarding")
@require_login_role(Role.ONBOARDING)
def onboarding():
    """Render the onboarding page"""
    return render_template("onboarding_wizard.html")


@page.route("/onboarding/check_membership")
@require_login_role(Role.ONBOARDING)
def onboarding_check_membership():
    """Lookup the new member and ensure their membership is active in Neon"""
    email = request.args.get("email")
    m = neon.search_member(email.strip())
    print(m)
    return {
        "neon_id": m["Account ID"],
        "first": m["First Name"],
        "last": m["Last Name"],
        "status": m["Account Current Membership Status"],
        "level": m["Membership Level"],
        "discord_user": m["Discord User"],
    }


@page.route("/onboarding/coupon")
@require_login_role(Role.ONBOARDING)
def onboarding_create_coupon():
    """Create a $45 coupon for classes - promotion for new members"""
    email = request.args.get("email")
    m = neon.search_member(email.strip())
    code = f"NM-{m['Last Name'].upper()[:3]}{int(time.time())%1000}"
    print("Creating coupon code", code)
    return neon.create_coupon_code(code, 45)


@page.route("/onboarding/discord_member_add")
@require_login_role(Role.ONBOARDING)
def discord_member_add():
    """Add the new member to the 'members' discord role, set their nickname,
    and tag their Neon account with their discord handle"""
    name = request.args.get("name", "")
    neon_id = request.args.get("neon_id", "")
    nick = request.args.get("nick", "")
    if name == "" or neon_id == "" or nick == "":
        return "Require params: name, neon_id, nick"

    print(neon.set_discord_user(neon_id, name))

    result = comms.set_discord_role(name, "Members")
    if result is False:
        return "Failed to grant Members role: member not found"

    result = comms.set_discord_nickname(name, nick)
    if result is False:
        return "Failed to set nickname: member not found"
    if result is True:
        return "Setup complete"

    return result


@page.route("/discord")
def discord_redirect():
    """Redirect users to the discord invite link"""
    return redirect("https://discord.gg/twmKh749aH")
