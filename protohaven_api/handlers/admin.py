"""Administrative pages and endpoints"""

import logging

from flask import Blueprint, Response, request

from protohaven_api.automation.membership import membership as memauto
from protohaven_api.config import get_config
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


def _get_account_details(account_id):
    """Gets the matching email for a Neon account, by ID"""
    content = neon.fetch_account(
        account_id,
    )
    if not content:
        raise RuntimeError(f"Failed to fetch account id {account_id}")
    content = content.get("individualAccount", None) or content.get("companyAccount")
    content = content.get("primaryContact", {})

    auto_field_present = False
    auto_field_value = None
    for cf in content.get("accountCustomFields", []):
        if cf["name"] == "Account Automation Ran":
            auto_field_present = True
            auto_field_value = cf.get("optionValues")

    return {
        "fname": content.get("First Name"),
        "email": content.get("email1")
        or content.get("email2")
        or content.get("email3"),
        "auto_field_present": auto_field_present,
        "auto_field_value": auto_field_value,
    }


@page.route("/admin/neon_membership_created_callback", methods=["POST"])
def neon_membership_created_callback():
    """Called whenever a new membership is created in Neon CRM.

    See https://developer.neoncrm.com/api/webhooks/membership-webhooks/
    """
    if get_config("neon/webhooks/new_membership/enabled", False) is True:
        return Response("Membership initializer disabled via config", status=200)
    roles = roles_from_api_key(request.json.get("customParameters", {}).get("api_key"))
    if Role.ADMIN not in roles:
        return Response("Not authorized", status=400)
    data = request.json["data"]["membership"]
    account_id = data.get("accountId")
    membership_id = data.get("membershipId")
    membership_name = data.get("membershipName")
    fee = float(data.get("fee"))
    enrollment = data.get("enrollmentType")
    txn_status = data.get("status")
    log.info(
        f"NeonCRM new_membership callback: #{membership_id} (account #{account_id}) "
        f"{membership_name} for ${fee} ({enrollment} {txn_status})"
    )

    if fee < 10:
        log.info(f"Skipping init of atypical membership of ${fee}")
        return Response("Fee below threshold", 400)

    # We must make sure this is the only (i.e. first) membership for the account
    num_memberships = len(list(neon.fetch_memberships(account_id)))
    if num_memberships == 1:
        details = _get_account_details(account_id)
        if not details["auto_field_present"] or details["auto_field_value"] is not None:
            log.info(
                f"Skipping init of membership with auto_field_present="
                f"{details['auto_field_present']}, value={details['auto_field_value']}"
            )
            return Response("Field error", status=400)
        msg = memauto.init_membership(
            account_id=account_id, email=details["email"], fname=details["fname"]
        )
        if msg:
            comms.send_email(msg.subject, msg.body, details["email"], msg.html)
            log.info(f"Sent to {details['email']}: '{msg.subject}'")
            airtable.log_comms(
                "neon_new_member_webhook", details["email"], msg.subject, "Sent"
            )
            log.info("Logged to airtable")
    else:
        log.info(
            "Member has {num_memberships} memberships; skipping new member init automation"
        )
        return Response("not a new member", status=200)
    return Response("ok", status=200)
