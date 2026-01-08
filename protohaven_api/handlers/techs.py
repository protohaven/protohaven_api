"""Site for tech leads to manage shop techs"""

import datetime
import logging
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, Response, current_app, redirect, request, session

from protohaven_api.automation.classes import events as eauto
from protohaven_api.automation.techs import techs as tauto
from protohaven_api.config import safe_parse_datetime, tz, tznow
from protohaven_api.integrations import airtable, comms, neon, neon_base, sales, wiki
from protohaven_api.integrations.models import Role
from protohaven_api.rbac import am_lead_role, am_neon_id, am_role, require_login_role

page = Blueprint("techs", __name__, template_folder="templates")


log = logging.getLogger("handlers.techs")


@page.route("/tech_lead")
def techs_selector():
    """Used previously. This redirects to the new endpoint"""
    return redirect("/techs")


@page.route("/techs")
def techs_dash():
    """Return svelte compiled static page for dashboard"""
    return current_app.send_static_file("svelte/techs.html")


@page.route("/_app/immutable/<typ>/<path>")
def techs_dash_svelte_files(typ, path):
    """Return svelte compiled static page for dashboard"""
    return current_app.send_static_file(f"svelte/_app/immutable/{typ}/{path}")


TECH_ONLY_PREFIX = "(SHOP TECH ONLY)"

# Some areas we exclude from results as they are never needed during operations.
EXCLUDED_AREAS = [
    "Back Yard",
    "Kitchen",
    "Digital",
    "Design Hub",
    "Fishbowl",
    "Hand Tools",
    "Staff Room",
    "Maintenance",
    "Conference Room",
    "Design Classroom",
    "Class Supplies",
    "Custodial Room",
    "Rack Storage",
    "Restroom 1",
    "Restroom 2",
]


def _fetch_tool_areas():
    return {
        a["fields"]["Name"].strip()
        for a in airtable.get_areas()
        if a["fields"]["Name"] not in EXCLUDED_AREAS
    }


def _fetch_tool_states(now):
    tool_states = []
    now = now.astimezone(tz)
    for t in airtable.get_tools():
        status = t["fields"].get("Current Status") or "Unknown"
        msg = t["fields"].get("Status Message") or "Unknown"
        modified = t["fields"].get("Status last modified")
        date = modified or ""
        if modified:
            modified = (now - safe_parse_datetime(modified)).days
            date = safe_parse_datetime(date).strftime("%Y-%m-%d")
        else:
            modified = 0
        tool_states.append(
            {
                "status": status,
                "name": t["fields"]["Tool Name"],
                "area": t["fields"]["Name (from Shop Area)"],
                "code": (
                    t["fields"]["Tool Code"].strip().upper()
                    if t["fields"]["Tool Code"]
                    else None
                ),
                "modified": modified,
                "message": msg,
                "date": date,
            }
        )
    return tool_states


@page.route("/techs/tool_state")
def techs_tool_state():
    """Fetches info on current state of tools"""
    return _fetch_tool_states(tznow())


@page.route("/techs/docs_state")
def techs_docs_state():
    """Fetches the state of documentation for all tool pages in the wiki"""
    return wiki.get_tool_docs_summary()


@page.route("/techs/members")
@require_login_role(Role.SHOP_TECH, redirect_to_login=False)
def techs_members():
    """Fetches today's sign-in information for members"""
    start = request.values.get("start")
    start = (safe_parse_datetime(start) if start else tznow()).replace(
        hour=0, minute=0, second=0, tzinfo=tz
    )
    end = start.replace(hour=23, minute=59, second=59)
    log.info(f"Fetching signins from {start} to {end}")
    return [
        {
            k: getattr(s, k)
            for k in (
                "name",
                "status",
                "email",
                "member",
                "clearances",
                "violations",
                "created",
            )
        }
        for s in airtable.get_signins_between(start, end)
    ]


@page.route("/techs/area_leads")
def techs_area_leads():
    """Fetches the mapping of areas to area leads"""
    areas = _fetch_tool_areas()
    area_map = {a: [] for a in areas}
    extras_map = defaultdict(list)

    fields = [
        "First Name",
        neon.CustomField.AREA_LEAD,
    ]

    if am_role(Role.SHOP_TECH) or am_lead_role():
        fields = fields + [
            "Last Name",
            "Preferred Name",
            "Email 1",
            neon.CustomField.PRONOUNS,
            neon.CustomField.SHOP_TECH_SHIFT,
        ]

    for t in neon.search_members_with_role(Role.SHOP_TECH, fields):
        for a in t.area_lead:
            data = {"name": t.name, "email": t.email, "shift": t.shop_tech_shift}
            if a not in area_map:
                extras_map[a].append(data)
            else:
                area_map[a].append(data)
    return {"area_leads": area_map, "other_leads": dict(extras_map)}


DEFAULT_FORECAST_LEN = 14


@page.route("/techs/forecast")
def techs_forecast():
    """Provide advance notice of the level of staffing of tech shifts"""
    date = request.args.get("date")
    if date is None:
        date = tznow()
    else:
        date = safe_parse_datetime(date)
    date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    forecast_len = int(request.args.get("days", DEFAULT_FORECAST_LEN))
    if forecast_len <= 0:
        return Response("Nonzero days required for forecast", status=400)
    result = tauto.generate(
        date, forecast_len, include_pii=am_role(Role.SHOP_TECH) or am_lead_role()
    )
    # Extract names from Member class objects
    for d in result["calendar_view"]:
        for ap in ("AM", "PM"):
            d[ap]["people"] = [p.name for p in d[ap]["people"]]
            if "ovr" in d[ap]:
                d[ap]["ovr"]["orig"] = [p.name for p in d[ap]["ovr"]["orig"]]
    return result


def _remove_discord_formatting(s: str) -> str:
    return re.sub(r"[_*#]", "", s.replace("\n", ""))


def _notify_override(name, shift, techs):
    """Sends notification of state of class to the techs and instructors channels
    when a tech (un)registers to backfill a class."""
    techs = [
        _remove_discord_formatting(t) for t in techs
    ]  # Remove formatting to allow for bold syntax
    msg = (
        f"**On duty {shift}: {', '.join(techs)}** "
        f"({name} edited via [/techs](https://api.protohaven.org/techs#cal))"
    )
    comms.send_discord_message(msg, "#techs", blocking=False)


@page.route("/techs/forecast/override", methods=["POST", "DELETE"])
@require_login_role(Role.SHOP_TECH, redirect_to_login=False)
def techs_forecast_override():
    """Update/remove forecast overrides on shop tech forecast"""
    data = request.json
    _id = data.get("id")
    fullname = data.get("fullname")
    date = data.get("date")
    ap = data.get("ap")
    techs = data.get("techs")
    orig = data.get("orig")
    if request.method == "POST":
        status, content = airtable.set_forecast_override(
            _id,
            date,
            ap,
            techs,
            data.get("email"),
            fullname,
        )
        if status != 200:
            return Response(content, status=status)
        _notify_override(fullname, f"{date} {ap}", techs)
        return content
    if request.method == "DELETE":
        ret = airtable.delete_forecast_override(data["id"])
        if ret:
            _notify_override(fullname, f"{date} {ap}", orig)
        return ret

    return Response(f"Method {request.method} not supported", status=400)


@page.route("/techs/list")
def techs_list():
    """Fetches tech info and lead status of observer"""
    fields = [
        "First Name",
    ]
    if am_role(Role.SHOP_TECH) or am_lead_role():
        fields += [
            "Email 1",
            "Last Name",
            "Preferred Name",
            neon.CustomField.PRONOUNS,
            neon.CustomField.SHOP_TECH_SHIFT,
            neon.CustomField.SHOP_TECH_FIRST_DAY,
            neon.CustomField.SHOP_TECH_LAST_DAY,
            neon.CustomField.AREA_LEAD,
            neon.CustomField.INTEREST,
            neon.CustomField.EXPERTISE,
            neon.CustomField.CLEARANCES,
        ]
    techs_results = []
    for m in neon.search_members_with_role(
        Role.SHOP_TECH, fields, merge_bios=airtable.get_all_tech_bios()
    ):
        t = {
            k: getattr(m, k)
            for k in (
                "name",
                "email",
                "clearances",
                "shop_tech_first_day",
                "shop_tech_last_day",
                "area_lead",
                "interest",
                "expertise",
                "shop_tech_shift",
                "volunteer_bio",
                "volunteer_picture",
            )
        }
        t["id"] = m.neon_id
        # Convert back from date so it's properly displayed as text
        if t["shop_tech_first_day"] is not None:
            t["shop_tech_first_day"] = t["shop_tech_first_day"].strftime("%Y-%m-%d")
        if t["shop_tech_last_day"] is not None:
            t["shop_tech_last_day"] = t["shop_tech_last_day"].strftime("%Y-%m-%d")
        techs_results.append(t)

    return {"tech_lead": am_role(Role.SHOP_TECH_LEAD), "techs": techs_results}


@page.route("/techs/update", methods=["POST"])
@require_login_role(Role.SHOP_TECH_LEAD, Role.SHOP_TECH, redirect_to_login=False)
def tech_update():
    """Update the custom fields of a shop tech in Neon"""
    data = request.json
    nid = data["id"]

    editable_fields = (
        "shop_tech_shift",
        "area_lead",
        "interest",
        "expertise",
        "shop_tech_first_day",
        "shop_tech_last_day",
    )
    if not am_role(Role.SHOP_TECH_LEAD):
        if not am_neon_id(nid):
            return Response("Access Denied", status=401)

        # Techs editing their own data can only edit a subset of fields
        editable_fields = ("interest", "expertise")

    body = {k: v for k, v in data.items() if k in editable_fields}
    return neon.set_tech_custom_fields(nid, **body)


@page.route("/techs/new_event", methods=["POST"])
@require_login_role(
    Role.SHOP_TECH_LEAD, Role.EDUCATION_LEAD, Role.STAFF, redirect_to_login=False
)
def new_tech_event():
    """Create a new techs-only event in Neon"""
    data = request.json
    log.info(f"new_event with data {data}")
    if str(data["name"]).strip() == "":
        log.info("Name field required")
        return Response("name field is required", status=401)
    log.info("Parsing date")
    d = safe_parse_datetime(data["start"]).replace(tzinfo=tz)
    hours = int(data["hours"])
    log.info(f"Parsed {d}, hours {hours}")
    if not d or d < tznow() or d.hour < 10 or d.hour + hours > 22:
        return Response(
            "start must be set to a valid date in the future and within business hours (10AM-10PM)",
            status=401,
        )
    log.info("checking capacity")
    capacity = int(data["capacity"])
    if capacity < 0 or capacity > 100:
        return Response("capacity field invalid", status=401)
    log.info(f"Creating event with data {data}")
    return neon_base.create_event(
        name=f"{TECH_ONLY_PREFIX} {data['name']}",
        desc="Tech-only event; created via api.protohaven.org/techs dashboard",
        start=d,
        end=d + datetime.timedelta(hours=hours),
        max_attendees=capacity,
        dry_run=False,
        published=False,  # Do NOT show this in the regular event browser
        registration=True,
        free=True,  # Do not apply pricing
    )


@page.route("/techs/rm_event", methods=["POST"])
@require_login_role(
    Role.SHOP_TECH_LEAD, Role.EDUCATION_LEAD, Role.STAFF, redirect_to_login=False
)
def rm_tech_event():
    """Delete a techs-only event in Neon"""
    data = request.json
    eid = str(data["eid"])
    if eid.strip() == "":
        return Response("eid field required", status=401)
    evt = neon.fetch_event(eid)
    if not evt:
        return Response(f"event with eid {eid} not found", status=404)
    if not evt.name.startswith(TECH_ONLY_PREFIX):
        return Response(
            f"cannot delete a non-tech-only event missing prefix {TECH_ONLY_PREFIX}",
            status=400,
        )

    return neon.set_event_scheduled_state(evt.neon_id, scheduled=False)


@page.route("/techs/enroll", methods=["POST"])
@require_login_role(Role.SHOP_TECH_LEAD, redirect_to_login=False)
def techs_enroll():
    """Enroll a Neon account in the shop tech program, via email"""
    data = request.json
    return neon.patch_member_role(data["email"], Role.SHOP_TECH, data["enroll"])


@page.route("/techs/events")
def techs_backfill_events():
    """Returns the list of available events for tech backfill.
    Logic matches automation.classes.builder.Action.FOR_TECHS
    """
    for_techs = []
    now = tznow()

    def _keep(evt):
        if evt.in_blocklist():
            return False
        tech_only_event = evt.name.startswith(TECH_ONLY_PREFIX) and evt.registration
        tech_backfill_event = (
            evt.published
            and evt.registration
            and evt.start_date - datetime.timedelta(days=1) < now < evt.start_date
        )

        if not tech_only_event and not tech_backfill_event:
            return False

        return True

    # Should dedupe logic with builder.py eventually.
    # We look for unpublished events too since those may be tech events
    for evt in eauto.fetch_upcoming_events(
        published=False, merge_airtable=True, fetch_attendees=_keep, fetch_tickets=_keep
    ):
        if not _keep(evt):
            continue

        # attendee_count requires attendee data to have been fetched,
        # so we have to additionally check here
        if evt.name.startswith(TECH_ONLY_PREFIX) or evt.attendee_count > 0:
            for_techs.append(
                {
                    "id": evt.neon_id,
                    "ticket_id": evt.single_registration_ticket_id,
                    "name": evt.name,
                    "attendees": list(evt.signups),
                    "capacity": evt.capacity,
                    "start": evt.start_date.isoformat(),
                    "supply_cost": evt.supply_cost or 0,
                }
            )

    return {
        "events": for_techs,
        "can_register": am_role(Role.SHOP_TECH) or am_role(Role.SHOP_TECH_LEAD),
        "can_edit": am_role(Role.SHOP_TECH_LEAD)
        or am_role(Role.EDUCATION_LEAD)
        or am_role(Role.STAFF),
    }


def _notify_registration(account_id, event_id, action):
    """Sends notification of state of class to the techs and instructors channels
    when a tech (un)registers to backfill a class."""
    acc = neon_base.fetch_account(account_id, required=True)
    evt = neon.fetch_event(event_id)
    attendees = {
        a["accountId"]
        for a in neon.fetch_attendees(event_id)
        if a["registrationStatus"] == "SUCCEEDED"
    }
    verb = "registered for"
    if action != "register":
        verb = "unregistered from"
    msg = (
        f"{acc.name} {verb} via [/techs](https://api.protohaven.org/techs#events) "
        f"{evt.name} on {evt.start_date.strftime('%a %b %d %-I:%M %p')} "
        f"; {evt.capacity - len(attendees)} seat(s) remain"
    )
    # Tech-only classes shouldn't bother instructors
    if not evt.name.startswith(TECH_ONLY_PREFIX):
        comms.send_discord_message(msg, "#instructors", blocking=False)
    comms.send_discord_message(msg, "#techs", blocking=False)


@page.route("/techs/event", methods=["POST"])
@require_login_role(Role.SHOP_TECH, redirect_to_login=False)
def techs_event_registration():
    """Enroll a Neon account in the shop tech program, via Neon ID"""
    account_id = session["neon_id"]
    data = request.json
    event_id = data.get("event_id")
    ticket_id = data.get("ticket_id")
    action = data.get("action")
    log.info(f"Attempt to (un)register for event: {account_id} {data}")
    if not account_id:
        return Response("Not logged in", status=401)
    if not event_id:
        return Response("event_id required", status=400)
    if not action in ("register", "unregister"):
        return Response("action must be one of 'register', 'unregister'", status=400)

    if action == "register":
        ret = neon.register_for_event(account_id, event_id, ticket_id)
    else:
        ret = neon.delete_single_ticket_registration(account_id, event_id) or {
            "status": "ok"
        }
    if ret:
        _notify_registration(account_id, event_id, action)
        return ret
    raise RuntimeError("Unknown error handling event registration state")


@page.route("/techs/storage_subscriptions", methods=["GET"])
@require_login_role(
    Role.SHOP_TECH_LEAD, Role.STAFF, Role.SHOP_TECH, redirect_to_login=False
)
def techs_storage_subscriptions():
    """Fetch tabular data about storage subscriptions in Square

    This offers a more "storage forward" interface vs Square, which is only
    sorted by customer name and shows a bunch of cancelled stuff too.
    """

    log.info("Async fetching subscription data")
    futures = []
    with ThreadPoolExecutor() as executor:
        futures.append(executor.submit(sales.get_subscription_plan_map))
        # We need the email despite PII limitations in order to lookup membership info
        futures.append(
            executor.submit(
                sales.get_customer_name_map, include_pii=True, include_email=True
            )
        )
        futures.append(executor.submit(sales.get_unpaid_invoices_by_id))

    sub_plan_map, cust_map, unpaid_invoices = [f.result() for f in futures]
    unpaid_invoices = dict(unpaid_invoices)
    log.info(f"Fetched map of {len(sub_plan_map)} subscriptions")
    log.info(f"Fetched {len(cust_map)} customers")
    log.info(f"Fetched {len(unpaid_invoices)} unpaid invoices")
    result = []
    log.info("Fetching and looping through subscriptions")
    for sub in sales.get_subscriptions():
        if sub["status"] != "ACTIVE":
            continue

        plan, price = sub_plan_map.get(
            sub["plan_variation_id"], (sub["plan_variation_id"], 0)
        )
        cust_name, cust_email = cust_map.get(sub["customer_id"]) or (
            sub["customer_id"],
            None,
        )

        # Also attempt to get the membership state, to identify non-members using storage.
        # We avoid re-fetching if missing because neon is heckin' slow and it times out the request
        mem_statuses = [
            (m.account_current_membership_status or None)
            for m in (neon.cache.get(cust_email, fetch_if_missing=False) or {}).values()
            if m.neon_id != m.company_id
        ]
        status = "Unknown"
        for check_status in ("Active", "Future", "Inactive"):
            if check_status in mem_statuses:
                status = check_status
                break

        result.append(
            {
                "id": sub["id"],
                "created_at": sub["created_at"],
                "start_date": sub["start_date"],
                "charged_through_date": sub["charged_through_date"],
                "monthly_billing_anchor_date": sub.get("monthly_billing_anchor_date")
                or "unknown",
                "customer": cust_name,
                "email": (
                    cust_email if am_lead_role() else None
                ),  # Only tech leads / admins
                "plan": plan,
                "price": price,
                "membership_status": status,
                "note": sub.get("note") or None,
                "unpaid": (
                    [i for i in sub["invoice_ids"] if i in unpaid_invoices]
                    if am_lead_role()
                    else []
                ),
            }
        )
    return result


@page.route("/techs/storage_subscriptions/<sub_id>/note", methods=["POST"])
@require_login_role(Role.SHOP_TECH, redirect_to_login=False)
def set_sub_note(sub_id):
    """Sets the note on a square subscription"""
    data = request.json
    note = data.get("note").strip()
    if not note or not sub_id:
        return Response("note and subscription ID reqiured", 400)
    log.info(f"Setting storage subscription {sub_id} note to {note}")
    return sales.set_subscription_note(sub_id, note)
