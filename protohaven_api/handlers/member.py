"""handlers for member pages"""

import datetime
import logging
import re
import threading
from typing import Any

from flask import Blueprint, Response, current_app, redirect, request, session

from protohaven_api.automation.roles.roles import setup_discord_user_sync
from protohaven_api.config import get_config
from protohaven_api.integrations import airtable, eventbrite, neon
from protohaven_api.integrations.airtable import NeonID, ToolCode
from protohaven_api.integrations.models import Role
from protohaven_api.rbac import am_role, require_login

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


def _fetch_neon_id() -> NeonID | Response:
    """Helper to grab Neon ID information from either the session, GET parameter,
    or JSON body of a POST request.

    For any instance where a non-session Neon ID is used, we confirm the logged in
    account is an administrator and can impersonate other Neon IDs in requests.
    """
    neon_id = None
    if request.content_type == "application/json":
        neon_id = str(request.json.get("neon_id"))

    neon_id = (neon_id or str(session.get("neon_id")) or "").strip()
    if not neon_id:
        return Response("You are not logged in", status=401)

    nid = (str(session.get("neon_id")) or "").strip()
    if nid != neon_id and not am_role(Role.ADMIN):
        return Response("Access Denied for admin parameter `neon_id`", status=401)
    return neon_id


@page.route("/member/set_discord", methods=["POST"])
@require_login
def set_discord_nick():
    """Set the nickname of a particular discord user"""
    discord_id = (request.json.get("discord_id") or "").strip()
    neon_id = _fetch_neon_id()
    if isinstance(neon_id, Response):
        return neon_id

    if not discord_id:
        return Response("discord_id field required", status=400)
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


def _recert_enabled(neon_id: NeonID):
    """As of 2026-01-31, recertification is still in testing and only enabled for
    certain opt-in test users"""
    enabled_users = get_config("general/recertification/enabled_users") or ""
    if not enabled_users:
        return False
    return re.match(enabled_users, neon_id)


@page.route("/member/recert_data", methods=["GET"])
@require_login
def get_recert_data():
    """Get recertification data for the logged in member"""
    neon_id = _fetch_neon_id()
    if isinstance(neon_id, Response):
        return neon_id

    if not _recert_enabled(neon_id):
        return Response("Not yet enabled", status=503)

    configs = airtable.get_tool_recert_configs_by_code()

    pending: list[tuple[ToolCode, datetime.datetime, dict[str, Any]]] = []
    for (
        nid,
        tool_code,
        inst_deadline,
        res_deadline,
        _,
    ) in airtable.get_pending_recertifications():
        if nid != neon_id:
            continue
        c = configs.get(tool_code)
        if not c:
            continue
        pending.append(
            (
                tool_code,
                max(inst_deadline, res_deadline).strftime("%Y-%m-%d"),
                c.as_dict(),
            )
        )
    pending.sort(key=lambda p: p[0])
    configs = [c.as_dict() for c in configs.values()]
    configs.sort(key=lambda c: c.get("tool"))
    return {"pending": pending, "configs": configs}


@page.route("/member/goto_class", methods=["GET"])
@require_login
def goto_class():
    """Redirect to a class based on its ID.
    If it's an eventbrite class, we also generate and apply an ephemeral and one-time use
    discount code based on the signed in session's membership type, income, and active status
    """
    orig_url = request.args.get("url")
    log.info(f"goto_class {orig_url}")

    # If not eventbrite, then it's a Neon event which uses logged-in session to apply discounts
    m = re.search(r"^https://www.eventbrite.com/e/(\d+).*", orig_url)
    if not m or not m.group(1):
        return redirect(orig_url)
    evt_id = m.group(1)

    log.info(f"Parsed event ID from url param: {evt_id}")
    if not eventbrite.is_valid_id(evt_id):
        # Redirect to original url if parsing fails, as a backup
        return redirect(orig_url)

    # PRECONDITION: Only valid eventbrite IDs past this point
    neon_id = _fetch_neon_id()
    if isinstance(neon_id, Response):
        return neon_id
    m = neon.search_member_by_neon_id(
        neon_id,
        fields=[
            "Account Current Membership Status",
            "Membership Level",
            neon.CustomField.INCOME_BASED_RATE,
        ],
    )
    if not m:
        return Response(
            f"Error fetching membership for #{neon_id} - not found", status=400
        )
    url = f"https://www.eventbrite.com/e/{evt_id}/"
    percent_off = m.event_discount_pct()
    if percent_off > 0:
        log.info(
            f"Generating {percent_off}% discount for member #{neon_id} for eventbrite #{evt_id}"
        )
        code = eventbrite.generate_discount_code(evt_id, percent_off)
        url += f"?discount={code}"
        log.info(f"Generated code {code}; redirecting to {url}")
        # https://intercom.help/eventbrite-marketing/en/articles/7239804-create-a-code-that-gives-a-discount-or-reveals-hidden-tickets
    else:
        log.info(
            f"No discount eligible for member #{neon_id}; redirecting without code applied"
        )
    return redirect(url)
