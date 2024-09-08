"""Handlers for onboarding steps for new members"""
import logging
import time

from flask import Blueprint, Response, current_app, request

from protohaven_api.integrations import comms, neon
from protohaven_api.rbac import Role, require_login_role

page = Blueprint("onboarding", __name__, template_folder="templates")
ONBOARDING_DISCOUNT_AMT = 30


log = logging.getLogger("handlers.onboarding")


@page.route("/onboarding")
@require_login_role(Role.ONBOARDING)
def onboarding():
    """Return svelte compiled static page for onboarding wizard"""
    return current_app.send_static_file("svelte/onboarding.html")


@page.route("/onboarding/_app/immutable/<typ>/<path>")
def onboarding_svelte_files(typ, path):
    """Return svelte compiled static page"""
    return current_app.send_static_file(f"svelte/_app/immutable/{typ}/{path}")


@page.route("/join_discord.png")
def discord_qr():
    """Return svelte QR code image"""
    return current_app.send_static_file("svelte/join_discord.png")


@page.route("/onboarding/check_membership")
@require_login_role(Role.ONBOARDING)
def onboarding_check_membership():
    """Lookup the new member and ensure their membership is active in Neon"""
    email = request.args.get("email")
    mm = list(neon.search_member(email.strip()))
    if len(mm) == 0:
        return Response(f"Member with email {email} not found", status=404)
    return [
        {
            "neon_id": m["Account ID"],
            "first": m["First Name"],
            "last": m["Last Name"],
            "status": m["Account Current Membership Status"],
            "level": m["Membership Level"],
            "discord_user": m["Discord User"],
        }
        for m in mm
    ]


@page.route("/onboarding/onboarders")
@require_login_role(Role.ONBOARDING)
def onboarding_get_onboarders():
    """Get the list of neon accounts with onboarding role assigned"""
    return list(neon.get_members_with_role(Role.ONBOARDING, ["Email 1"]))


@page.route("/onboarding/coupon")
@require_login_role(Role.ONBOARDING)
def onboarding_create_coupon():
    """Create a coupon for classes - promotion for new members"""
    email = request.args.get("email")
    m = list(neon.search_member(email.strip()))
    if len(m) == 0:
        return Response(f"Member with email {email} not found", status=404)
    m = m[0]
    code = f"NM-{m['Last Name'].upper()[:3]}{int(time.time())%1000}"
    log.info(f"Creating coupon code: {code}")
    return {"coupon": neon.create_coupon_code(code, ONBOARDING_DISCOUNT_AMT)}


NOTFOUND_INFO = (
    "member not found in our Discord server. Make sure the "
    "user has joined via https://protohaven.org/discord"
)


@page.route("/onboarding/discord_member_add")
@require_login_role(Role.ONBOARDING)
def discord_member_add():
    """Add the new member to the 'members' discord role, set their nickname,
    and tag their Neon account with their discord handle"""
    name = request.args.get("name", "")
    neon_id = request.args.get("neon_id", "")
    nick = request.args.get("nick", "")
    if name == "" or neon_id == "" or nick == "":
        return Response("Require params: name, neon_id, nick", status=400)

    result = comms.set_discord_role(name, "Members")
    if result is False:
        return Response("Failed to grant Members role: " + NOTFOUND_INFO, status=404)

    result = comms.set_discord_nickname(name, nick)
    if result is False:
        return Response("Failed to set nickname: " + NOTFOUND_INFO, status=404)

    # Set the discord user after we know the member can be found
    rep = neon.set_discord_user(neon_id, name)
    log.info(f"neon.set_discord_user response: {rep}")

    return {"status": "Setup complete"}
