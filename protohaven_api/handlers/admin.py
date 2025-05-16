"""Administrative pages and endpoints"""

import json
import logging

from flask import Blueprint, Response, request, session

from protohaven_api.automation.membership import clearances as mclearance
from protohaven_api.automation.membership import membership as memauto
from protohaven_api.config import get_config
from protohaven_api.handlers.auth import login_with_neon_id
from protohaven_api.integrations import airtable, comms, mqtt, neon, neon_base, tasks
from protohaven_api.rbac import (
    Role,
    require_dev_environment,
    require_login_role,
    roles_from_api_key,
)

page = Blueprint("admin", __name__, template_folder="templates")

log = logging.getLogger("handlers.admin")


@page.route("/admin/login_as", methods=["GET"])
@require_dev_environment()
def login_as_user():
    """Force the browser session to a specific user (for dev)"""
    neon_id = int(request.values["neon_id"])
    log.warning(f"Logging in as user #{neon_id}")
    login_with_neon_id(neon_id)
    return session["neon_account"]


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

    delta = []
    if request.method != "GET":
        initial = [c.strip() for c in request.values.get("codes").split(",")]
        if len(initial) == 0:
            return Response("Missing required param 'codes'", status=400)
        delta = mclearance.resolve_codes(initial)

    for e in emails:
        try:
            results[e] = {
                "method": request.method,
                "delta": delta,
                "result": mclearance.update(e, request.method, delta),
                "status": 200,
            }
        except RuntimeError as exc:
            results[e] = {
                "method": request.method,
                "delta": delta,
                "result": [],
                "status": 500,
                "message": str(exc),
            }
        except KeyError as exc:
            results[e] = {
                "method": request.method,
                "delta": delta,
                "result": [],
                "status": 404,
                "message": str(exc),
            }
        except TypeError as exc:
            results[e] = {
                "method": request.method,
                "delta": delta,
                "result": [],
                "status": 400,
                "message": str(exc),
            }

    if request.method != "GET":
        comms.send_discord_message(
            "Member clearance updates:\n"
            + "\n".join([f"-{e}: {v}\n" for e, v in results.items()]),
            "#membership-automation",
            blocking=False,
        )

    return Response(
        json.dumps(results),
        content_type="application/json",
        status=max(r["status"] for r in results.values()),
    )


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
    try:
        msgs = memauto.init_membership(
            account_id=account_id,
            membership_name=membership_name,
            membership_id=membership_id,
            email=details["email"],
            fname=details["fname"],
        )
    except Exception:
        comms.send_discord_message(
            "ERROR initializing membership "
            f"[#{membership_id}](https://protohaven.app.neoncrm.com/"
            f"np/admin/account/membershipDetail.do?id={membership_id}) for "
            f"[#{account_id}](https://protohaven.app.neoncrm.com/admin/accounts/{account_id}) "
            f"({details['email']}, {details['fname']}); see server logs for details. "
            "Account intervention may be needed.",
            "#membership-automation",
            blocking=False,
        )
        raise
    for msg in msgs:
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
    if not tc:
        return Response("tool_code must be provided in request", 400)
    airtable_id, _ = airtable.get_tool_id_and_name(tc)
    log.info(f"Resolved {tc} -> {airtable_id}")
    if not airtable_id:
        return Response(f"Couldn't resolve airtable ID for tool code {tc}", 400)
    return {
        "history": sorted(
            airtable.get_reports_for_tool(airtable_id),
            key=lambda r: r["t"],
            reverse=True,
        ),
        "active_tasks": [
            {
                "name": "TODO",
                "modified_at": None,
                "gid": None,
            }
        ],
    }


@page.route("/admin/maintenance", methods=["POST"])
@require_login_role(Role.AUTOMATION)
def tool_maintenance_submission():
    """Handle maintenance changes due to user submission"""
    data = request.json
    reporter = data["reporter"]
    tools = data["tools"]
    status = data["status"]
    summary = data["summary"]
    detail = data["detail"]
    urgent = data["urgent"]
    images = data["images"]
    create_task = data["create_task"]

    if create_task is True:
        tasks.add_tool_report_task(tools, summary, status, images, reporter, urgent)

    msg = (
        f"New Tool Report by {reporter}:\n"
        f"Tool(s): {', '.join(tools)}\n"
        f"Status: {status} {'(URGENT) ' if urgent else ''}- {summary}\n\n"
        f"{detail}\n\n"
        "See [all history](https://airtable.com/appbIlORlmbIxNU1L"
        "/shrb58zUuDBmcmTNQ/tblZbQcalfrvUiNM6)"
    )
    comms.send_discord_message(msg, "#maintenance", blocking=False)
    for tool in tools:
        mqtt.notify_maintenance(tool, status, summary)

    return "OK"
