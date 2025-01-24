"""handlers for member pages"""

import logging
import threading

from flask import Blueprint, Response, current_app, request, session

from protohaven_api.automation.roles.roles import setup_discord_user_sync
from protohaven_api.integrations import neon
from protohaven_api.rbac import Role, am_role, require_login

page = Blueprint("member", __name__, template_folder="templates")

log = logging.getLogger("handlers.member")


@page.route("/member")
@require_login
def member():
    """Return svelte compiled static page for member dashboard"""
    return current_app.send_static_file("svelte/member.html")


@page.route("/member/_app/immutable/<typ>/<path>")
@require_login
def member_svelte_files(typ, path):
    """Return svelte compiled static page for member dashboard"""
    return current_app.send_static_file(f"svelte/_app/immutable/{typ}/{path}")


@page.route("/member/set_discord", methods=["POST"])
@require_login
def set_discord_nick():
    """Set the nickname of a particular discord user"""
    discord_id = (request.json.get("discord_id") or "").strip()
    neon_id = (request.json.get("neon_id") or session.get("neon_id") or "").strip()

    if not discord_id:
        return Response("discord_id field required", status=400)
    if not neon_id:
        return Response(
            "You must be logged in as the user you're attempting to change", status=401
        )

    if neon_id != "":
        nid = (session.get("neon_id") or "").strip()
        if nid != neon_id and not am_role(Role.ADMIN):
            return Response("Access Denied for admin parameter `neon_id`", status=401)
    result = neon.set_discord_user(neon_id, discord_id)
    if not result.get("accountId") == str(neon_id):
        return Response(
            f"Error setting discord user {discord_id} "
            "for neon user {neon_id}: {result}",
            500,
        )

    log.info(f"Starting setup on newly associated {discord_id} (#{neon_id})")
    threading.Thread(
        target=setup_discord_user_sync, daemon=True, args=(discord_id,)
    ).start()
    return result
