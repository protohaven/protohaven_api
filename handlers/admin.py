from flask import Blueprint, render_template, request

from integrations import airtable, neon
from rbac import Role, require_login_role

page = Blueprint("admin", __name__, template_folder="templates")


@page.route("/user/clearances", methods=["GET", "PATCH", "DELETE"])
@require_login_role(Role.ADMIN)
def user_clearances():
    emails = [e.strip() for e in request.values.get("emails", "").split(",")]
    if len(emails) == 0:
        raise Exception("require param emails")
    results = {}
    for e in emails:
        m = neon.search_member(e)
        if m is None:
            results[e] = "NotFound"
            continue
        neon_id = m["Account ID"]

        codes = set(neon.get_user_clearances(neon_id))
        if request.method == "GET":
            results[e] = list(codes)
            continue

        initial = [c.strip() for c in request.values.get("codes").split(",")]
        if len(initial) == 0:
            raise Exception("Require param codes")

        # Resolve clearance groups (e.g. MWB) into multiple tools (ABG, RBP, GDD, MCS, MDP, SHP, SBG, VMB)
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
            raise Exception(content)
        else:
            results[e] = "OK"
    return results


@page.route("/admin/user_clearances")
def admin_user_clearances():
    return render_template("admin_set_clearances.html")


@page.route("/admin/set_discord_nick")
@require_login_role(Role.ADMIN)
def set_discord_nick():
    name = request.args.get("name")
    nick = request.args.get("nick")
    if name == "" or nick == "":
        return "Bad argument: want ?name=foo&nick=bar"
    client = discord_bot.get_client()
    result = asyncio.run_coroutine_threadsafe(
        client.set_nickname(name, nick), client.loop
    ).result()
    print(result)
    if result == False:
        return f"Member '{name}' not found"
    else:
        return f"Member '{name}' now nicknamed '{nick}'"
