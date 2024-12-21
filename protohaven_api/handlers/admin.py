"""Administrative pages and endpoints"""

import logging

from flask import Blueprint, Response, request

from protohaven_api.automation.maintenance import tasks as mtask
from protohaven_api.automation.membership import membership as memauto
from protohaven_api.config import get_config
from protohaven_api.integrations import airtable, comms, neon, neon_base
from protohaven_api.rbac import Role, require_login_role, roles_from_api_key

page = Blueprint("admin", __name__, template_folder="templates")

log = logging.getLogger("handlers.admin")


@page.route("/user/clearances", methods=["GET", "PATCH", "DELETE"])
@require_login_role(Role.AUTOMATION)
def user_clearances():
    """CRUD operations for member clearances.
    used to update clearances when instructor submits logs"""
    emails = [
        e.strip()
        for e in request.values.get("emails", "").split(",")
        if e.strip() != ""
    ]
    log.info(request.values)
    if len(emails) == 0:
        return Response("Missing required param 'emails'", status=400)
    results = {}
    all_codes = neon.fetch_clearance_codes()
    name_to_code = {c["name"]: c["code"] for c in all_codes}
    code_to_id = {c["code"]: c["id"] for c in all_codes}
    for e in emails:
        m = list(neon.search_member(e))
        if len(m) == 0:
            results[e] = "NotFound"
            continue
        m = m[0]
        if m["Account ID"] == m["Company ID"]:
            return Response(
                f"Account with email {e} is a company; request invalid", status=400
            )
        print(m)

        codes = {
            name_to_code.get(n)
            for n in (m.get("Clearances") or "").split("|")
            if n != ""
        }
        if request.method == "GET":
            results[e] = [c for c in codes if c is not None]
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
            ids = {code_to_id[c] for c in codes if c in code_to_id.keys()}
            log.info(f"Setting clearances for {m['Account ID']} to {ids}")
            content = neon.set_clearances(m["Account ID"], ids, is_company=False)
            log.info("Neon response: %s", str(content))
        except RuntimeError as e:
            return Response(str(e), status=500)
        results[e] = "OK"
    return results


def _get_account_details(account_id):
    """Gets the matching email for a Neon account, by ID"""
    content, _ = neon_base.fetch_account(account_id, required=True)
    auto_field_value = None
    for cf in content.get("accountCustomFields", []):
        if cf["name"] == "Account Automation Ran":
            auto_field_value = cf.get("value")

    content = content.get("primaryContact", {})
    return {
        "fname": content.get("firstName") or "new member",
        "email": content.get("email1")
        or content.get("email2")
        or content.get("email3"),
        "auto_field_value": auto_field_value,
    }


@page.route("/admin/neon_membership_created_callback", methods=["POST"])
def neon_membership_created_callback():
    """Called whenever a new membership is created in Neon CRM.

    See https://developer.neoncrm.com/api/webhooks/membership-webhooks/
    """
    is_enabled = get_config(
        "neon/webhooks/new_membership/enabled", default=False, as_bool=True
    )
    if not is_enabled:
        log.info("Skipping new membership callback - not initialized")
        return Response("Membership initializer disabled via config", status=200)
    api_key = request.json.get("customParameters", {}).get("api_key")
    log.info("New membership callback received")
    roles = roles_from_api_key(api_key) or []
    if Role.AUTOMATION["name"] not in roles:
        log.warning("Membership callback not authorized; ignoring")
        return Response("Not authorized", status=400)

    data = request.json["data"]["membershipEnrollment"]
    account_id = data.get("accountId")
    membership_id = data.get("membershipId")
    membership_name = data.get("membershipName")
    fee = float(data.get("fee"))
    enrollment = data.get("enrollmentType")
    txn_status = request.json["data"]["transaction"].get("transactionStatus")
    log.info(
        f"NeonCRM new_membership callback: #{membership_id} (account #{account_id}) "
        f"{membership_name} for ${fee} ({enrollment} {txn_status})"
    )
    if fee < 10:
        log.info(f"Skipping init of atypical membership of ${fee}")
        return Response("Fee below threshold", 400)

    # We must make sure this is the only (i.e. first) membership for the account
    num_memberships = len(list(neon.fetch_memberships(account_id)))
    if num_memberships != 1:
        log.info(
            f"Member has {num_memberships} memberships; skipping new member init automation"
        )
        return Response("not a new member", status=200)

    details = _get_account_details(account_id)
    if details["auto_field_value"] is not None:
        log.info(
            f"Skipping init of membership with auto_field_value={details['auto_field_value']}"
        )
        return Response("Account already deferred", status=400)
    msg = memauto.init_membership(
        account_id=account_id,
        membership_id=membership_id,
        email=details["email"],
        fname=details["fname"],
    )
    if msg:
        comms.send_email(msg.subject, msg.body, [details["email"]], msg.html)
        log.info(f"Sent to {details['email']}: '{msg.subject}'")
        airtable.log_comms(
            "neon_new_member_webhook", details["email"], msg.subject, "Sent"
        )
        log.info("Logged to airtable")
    return Response("ok", status=200)


@page.route("/admin/get_maintenance_data", methods=["GET"])
@require_login_role(Role.AUTOMATION)
def get_maintenance_data():
    """Used by Bookstack wiki to populate a widget on tool wiki pages"""
    tc = request.values.get("tool_code")
    airtable_id, name = airtable.get_tool_id_and_name(tc)
    log.info(f"Resolved {tc} -> {airtable_id}")
    if not airtable_id:
        return Response(f"Couldn't resolve airtable ID for tool code {tc}", 400)
    return {
        "history": list(airtable.get_reports_for_tool(airtable_id)),
        "active_tasks": list(mtask.get_open_tasks_matching_tool(airtable_id, name)),
    }
