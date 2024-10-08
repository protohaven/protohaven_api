"""Administrative pages and endpoints"""

import logging

from flask import Blueprint, Response, render_template, request

from protohaven_api.integrations import airtable, comms, neon
from protohaven_api.rbac import Role, require_login_role, roles_from_api_key

page = Blueprint("admin", __name__, template_folder="templates")

log = logging.getLogger("handlers.admin")


@page.route("/user/clearances", methods=["GET", "PATCH", "DELETE"])
@require_login_role(Role.ADMIN)
def user_clearances():
    """CRUD operations for member clearances.
    used to update clearances when instructor submits logs"""
    emails = [
        e.strip()
        for e in request.values.get("emails", "").split(",")
        if e.strip() != ""
    ]
    if len(emails) == 0:
        return Response("Missing required param 'emails'", status=400)
    results = {}
    for e in emails:
        m = list(neon.search_member(e))
        if len(m) == 0:
            results[e] = "NotFound"
            continue
        neon_id = m[0]["Account ID"]

        codes = set(neon.get_user_clearances(neon_id))
        if request.method == "GET":
            results[e] = list(codes)
            continue

        initial = [c.strip() for c in request.values.get("codes").split(",")]
        if len(initial) == 0:
            return Response("Missing required param 'codes'", status=400)

        # Resolve clearance groups (e.g. MWB) into multiple tools (ABG, RBP...)
        mapping = airtable.get_clearance_to_tool_map()
        delta = []
        for c in initial:
            if c in mapping:
                delta += list(mapping[c])
            else:
                delta.append(c)

        if request.method == "PATCH":
            codes.update(delta)
        elif request.method == "DELETE":
            codes -= set(delta)
        try:
            content = neon.set_clearances(neon_id, codes)
            log.info("Neon response: %s", str(content))
        except RuntimeError as e:
            return Response(str(e), status=500)
        results[e] = "OK"
    return results


@page.route("/admin/user_clearances")
def admin_user_clearances():
    """Admin page for managing user clearances"""
    return render_template("admin_set_clearances.html")


@page.route("/admin/set_discord_nick")
@require_login_role(Role.ADMIN)
def set_discord_nick():
    """Set the nickname of a particular discord user"""
    name = request.args.get("name")
    nick = request.args.get("nick")
    if name == "" or nick == "":
        return "Bad argument: want ?name=foo&nick=bar"
    result = comms.set_discord_nickname(name, nick)
    if result is False:
        return f"Member '{name}' not found"
    return f"Member '{name}' now nicknamed '{nick}'"


@page.route("/admin/neon_membership_created_callback", methods=["POST"])
def neon_membership_created_callback():
    """Called whenever a new membership is created in Neon CRM.

    See https://developer.neoncrm.com/api/webhooks/membership-webhooks/
    """
    roles = roles_from_api_key(request.json.get("customParameters", {}).get("api_key"))
    if Role.ADMIN not in roles:
        return Response("Not authorized", status=400)
    data = request.json["data"]["membership"]
    membership_id = data.get("membershipId")
    account_id = data.get("accountId")
    membership_name = data.get("membershipName")
    fee = data.get("fee")
    enrollment = data.get("enrollmentType")
    txn_status = data.get("status")
    log.info(
        f"NeonCRM new_membership callback: #{membership_id} (account #{account_id}) "
        f"{membership_name} for ${fee} ({enrollment} {txn_status})"
    )
    return "TODO"
