"""Administrative pages and endpoints"""

import logging

from flask import Blueprint, render_template, request

from protohaven_api.integrations import airtable, comms, neon
from protohaven_api.rbac import Role, require_login_role

page = Blueprint("admin", __name__, template_folder="templates")

log = logging.getLogger("handlers.admin")


@page.route("/user/clearances", methods=["GET", "PATCH", "DELETE"])
@require_login_role(Role.ADMIN)
def user_clearances():
    """CRUD operations for member clearances"""
    emails = [e.strip() for e in request.values.get("emails", "").split(",")]
    if len(emails) == 0:
        raise RuntimeError("require param emails")
    results = {}
    for e in emails:
        m = neon.search_member(e)
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
            raise RuntimeError("Require param codes")

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
        print(e, codes)
        rep, content = neon.set_clearances(neon_id, codes)
        if rep.status != 200:
            raise RuntimeError(content)
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
    print(result)
    if result is False:
        return f"Member '{name}' not found"
    return f"Member '{name}' now nicknamed '{nick}'"


@page.route("/admin/discord/all_members_and_roles")
def sync_discord_roles():
    """Endpoint to expose discord bot fetch request for members and roles"""
    return comms.get_all_members_and_roles()
