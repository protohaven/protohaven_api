# pylint: disable=duplicate-code
"""handlers for main landing page"""

import datetime
import json
import logging
import time

from flask import Blueprint, Response, current_app, redirect, request, session
from flask_sock import Sock

from protohaven_api.automation.classes import events as eauto
from protohaven_api.automation.membership import sign_in
from protohaven_api.config import get_config, safe_parse_datetime, tznow
from protohaven_api.integrations import airtable, booked, mqtt, neon
from protohaven_api.integrations.models import Event, Member
from protohaven_api.integrations.schedule import fetch_shop_events
from protohaven_api.rbac import Role, require_login, require_login_role

page = Blueprint("index", __name__, template_folder="templates")

log = logging.getLogger("handlers.index")


@page.route("/")
@require_login
def index():
    """Redirect to the member page"""
    return redirect("/member")


@page.route("/whoami")
def whoami():
    """Returns data about the logged in user"""
    neon_account = session.get("neon_account")
    if not neon_account:
        return Response("You are not logged in", status=400)
    acct = Member.from_neon_fetch(neon_account)
    return {
        "fullname": acct.name,
        "email": acct.email,
        "neon_id": acct.neon_id,
        "clearances": acct.clearances,
        "roles": [v["name"] for v in (acct.roles or [])],
        "event_discount_pct": acct.event_discount_pct(),
    }


@page.route("/event_ticker")
def event_ticker():
    """Get upcoming events for advertisement purposes"""
    return neon.get_sample_classes(int(time.time()) // 3600, until=30)


@page.route("/welcome/_app/immutable/<typ>/<path>")
def welcome_svelte_files(typ, path):
    """Return svelte compiled static pages for welcome page"""
    return current_app.send_static_file(f"svelte/_app/immutable/{typ}/{path}")


@page.route("/logo_color.svg")
def welcome_logo():
    """Return svelte compiled static pages for welcome page"""
    return current_app.send_static_file("svelte/logo_color.svg")


def welcome_sock(ws):
    """Websocket for handling front desk sign-in process. Status is reported back periodically"""
    data = json.loads(ws.receive())

    def _send(msg, pct):
        ws.send(json.dumps({"msg": msg, "pct": pct}))

    if data["person"] == "member":
        result = sign_in.as_member(data, _send)
    else:  # if data["person"] == "guest":
        result = sign_in.as_guest(data)

    if result.get("status") == "Active":
        mqtt.notify_member_signed_in(result.get("neon_id"))
    ws.send(json.dumps(result))
    return result


def welcome_neon_ws(ws):
    """Persistent websocket that listens for Neon ID badge scans via MQTT.
    When a Neon ID is published on the configured MQTT topic, it is forwarded
    to the Svelte frontend to trigger the sign-in flow."""
    neon_signin_topic = get_config("mqtt/neon_signin_topic")
    log.info(f"Neon sign-in WS connected; subscribing to MQTT topic: {neon_signin_topic}")

    # Queue for inter-thread communication
    import queue

    msg_queue = queue.Queue()

    def on_neon_signin(topic, data):
        """Callback when MQTT message arrives on neon signin topic"""
        # Extract Neon ID from topic or payload
        # Topic format: protohaven_api/v1/user/{neon_id}/signin
        neon_id = data.get("neon_id") if isinstance(data, dict) else None
        if not neon_id:
            # Try extracting from topic (last segment before /signin is the neon_id)
            parts = topic.split("/")
            try:
                signin_idx = parts.index("signin")
                neon_id = parts[signin_idx - 1]
            except (ValueError, IndexError):
                log.warning(f"Could not extract neon_id from topic: {topic}")
                return
        neon_id = str(neon_id)

        # Look up the member's email from Neon
        email = None
        try:
            m = neon.search_member_by_neon_id(neon_id)
            if m:
                email = m.email
                log.info(f"Neon sign-in via MQTT: neon_id={neon_id}, email={email}")
            else:
                log.warning(f"Neon sign-in via MQTT: member not found for neon_id={neon_id}")
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.warning(f"Error looking up neon_id={neon_id}: {e}")

        msg_queue.put({"neon_id": neon_id, "email": email})

    mqtt_client = mqtt.get()
    if mqtt_client and neon_signin_topic:
        mqtt_client.register_topic_callback(neon_signin_topic, on_neon_signin)

    try:
        while True:
            # Check if the client has closed the connection
            try:
                data = ws.receive(timeout=0.1)
                if data is None:
                    break
                # Client can send ping/pong or other messages; echo for now
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    ws.send(json.dumps({"type": "pong"}))
            except Exception:
                pass

            # Check for MQTT messages
            try:
                msg = msg_queue.get_nowait()
                ws.send(json.dumps({"type": "neon_id", **msg}))
            except queue.Empty:
                pass
    finally:
        # Clean up: unregister the callback
        if mqtt_client and neon_signin_topic:
            mqtt_client.unregister_topic_callback(neon_signin_topic, on_neon_signin)
        log.info("Neon sign-in WS disconnected")

    return None


def setup_sock_routes(app):
    """Set up all websocket routes; called by main.py"""
    sock = Sock(app)
    sock.route("/welcome/ws")(welcome_sock)
    sock.route("/welcome/neon_ws")(welcome_neon_ws)


@page.route("/welcome", methods=["GET"])
def welcome_signin():
    """Sign-in page at front desk"""
    return current_app.send_static_file("svelte/welcome.html")


@page.route("/welcome/announcement_ack", methods=["POST"])
def acknowledge_announcements():
    """Set the acknowledgement date to `now` so prior announcements
    are no longer displayed"""
    data = request.json
    m = list(neon.search_members_by_email(data["email"]))
    if len(m) == 0:
        raise KeyError("Member not found")
    neon.update_announcement_status(m[0].neon_id)
    return {"status": "OK"}


@page.route("/welcome/survey_response", methods=["POST"])
def survey_response():
    """Set the acknowledgement date to `now` so prior announcements
    are no longer displayed"""
    data = request.json

    neon_id = None
    m = list(neon.search_members_by_email(data["email"]))
    if len(m) != 0:
        neon_id = m[0].neon_id
    status, content = airtable.insert_simple_survey_response(
        data["rec_id"], data["email"], neon_id, data["response"]
    )
    if status != 200:
        log.error(f"Survey response error {status}: {content}")
    return Response(json.dumps({"status": status}), status=status)


@page.route("/class_listing", methods=["GET"])
def class_listing():
    """Returns a list of classes that are upcoming"""
    result = []
    for evt in eauto.fetch_upcoming_events(back_days=0, merge_airtable=True):
        result.append(
            {
                "id": evt.event_id,
                "name": evt.name,
                "timestamp": evt.start_date.isoformat(),
                "description": evt.description,
                "day": evt.start_date.strftime("%A, %b %-d"),
                "time": evt.start_date.strftime("%-I:%M %p"),
                "airtable_data": evt.airtable_data,
            }
        )
    result.sort(key=lambda c: c["timestamp"])
    return result


@require_login_role(
    Role.SHOP_TECH_LEAD,
    Role.STAFF,
    Role.EDUCATION_LEAD,
    Role.SHOP_TECH,
    redirect_to_login=False,
)
@page.route("/neon_lookup", methods=["POST"])
def neon_id_lookup():
    """Look up basic info of a user in Neon based on a search by name or email"""
    result = []
    search = request.values.get("search")
    if search is None:
        log.info("No search data provided")
        return result
    for i in neon.cached_find_best_match(
        search, score_cutoff=int(request.values.get("min_score") or 65)
    ):
        result.append(
            {
                "neon_id": i.neon_id,
                "name": f"{i.fname} {i.lname}",
                "email": i.email,
                "display": f"{i.fname} {i.lname} (#{i.neon_id})",
            }
        )
    return result


@page.route("/events", methods=["GET"])
def events_static():
    """Events dashboard"""
    return current_app.send_static_file("svelte/events.html")


@page.route("/events/_app/immutable/<typ>/<path>")
def events_svelte_files(typ, path):
    """Return svelte compiled static pages for welcome page"""
    return current_app.send_static_file(f"svelte/_app/immutable/{typ}/{path}")


@page.route("/events/attendees")
def events_dashboard_attendee_count():
    """Gets the attendee count for a given event, by its neon ID"""
    event_id = request.args.get("id")
    if event_id is None:
        raise RuntimeError("Requires param id")
    evt = eauto.fetch_event(event_id, attendees=True)
    if evt:
        return str(evt.attendee_count)
    return "0"


@page.route("/events/tickets")
def event_ticket_info():
    """Gets the attendee count for a given event, by its neon ID"""
    event_id = request.args.get("id")
    if event_id is None:
        raise RuntimeError("Requires param id")
    evt = eauto.fetch_event(event_id, tickets=True)
    tickets = []
    for t in evt.ticket_options:
        # While this is technically a no-op, it's a reminder that this response
        # format is expected to have exactly these fields when fetched from the
        # protohaven-events wordpress plugin.
        tickets.append({k: t[k] for k in ("id", "name", "price", "total", "sold")})
    return tickets


def humanize_sessions(evt: Event) -> str | None:
    """Humanized version of timing info based on
    the session data from Airtable"""
    if not evt.airtable_data:
        return None
    ss = evt.sessions
    if len(ss) == 0:
        return None

    durations = {round((s[1] - s[0]).total_seconds() / 60 / 60, 1) for s in ss}
    d = list(durations)[0]
    dstr = str(int(d) if d % 1 == 0 else round(d, 1))

    if len(durations) == 1 and len(ss) == 1:
        return f"Single {dstr}h Class"
    if len(durations) != 1:
        return f"{len(ss)} Sessions, Various Times"

    # Else single duration for all sessions
    return f"{len(ss)} Sessions, {dstr}h Each"


@page.route("/events/upcoming")
def upcoming_events():
    """Show relevant upcoming events."""
    events = []
    now = tznow()
    for evt in eauto.fetch_upcoming_events(merge_airtable=True):
        # Don't list private instruction, expired classes,
        # or classes without dates
        if not evt.start_date or evt.in_blocklist() or evt.end_date < now:
            continue
        events.append(
            {
                "id": evt.event_id,
                "name": evt.name,
                "description": evt.description,
                "instructor": evt.instructor_name,
                "start": evt.start_date.isoformat(),
                "end": evt.end_date.isoformat(),
                # Javascript is atrocious at correctly formatting
                # dates and times; we do this in python for EST/EDT consistency
                # across browsers and locale settings
                "humanized_start": evt.start_date.strftime("%a, %b %d, %I:%M%p"),
                "humanized_session_info": humanize_sessions(evt),
                "category": evt.display_category,
                "level": evt.display_level,
                "capacity": evt.capacity,
                "url": evt.url,
                "image_url": evt.image_url,
                "registration": evt.registration
                and evt.start_date - datetime.timedelta(hours=24) > now,
            }
        )

    events.sort(key=lambda e: e["start"])
    return {"now": now.isoformat(), "events": events}


@page.route("/events/shop")
def get_shop_events():
    """Show shop events."""
    shop_events = []
    for e, dates in fetch_shop_events().items():
        for start, _ in dates:
            start = safe_parse_datetime(start)
            shop_events.append({"name": e, "start": start})
    shop_events.sort(key=lambda v: v["start"])
    return shop_events


@page.route("/events/reservations")
def get_event_reservations():
    """Show reservations for the rest of the day."""
    reservations = []
    now = tznow()

    for r in booked.cache["reservations"]:
        start = r["startDate"]
        end = r["endDate"]
        open_time = now.replace(hour=10, minute=0, second=0, microsecond=0)
        close_time = now.replace(hour=22, minute=0, second=0, microsecond=0)
        tool_area, tool_name = [t.strip() for t in r["resourceName"].split("-", 1)]

        # We specifically want to include reservations
        # that have started but are still active.
        # We do NOT want reservations which are already over.
        if end > now:
            reservations.append(
                {
                    "ts": start.isoformat(),
                    "start": (
                        start.strftime("%-I:%M %p") if start > open_time else "open"
                    ),
                    "end": end.strftime("%-I:%M %p") if end < close_time else "close",
                    "name": f"{r['firstName']} {r['lastName']}",
                    "resource": tool_name,
                    "id": r["referenceNumber"],
                    "area": tool_area,
                }
            )
    return reservations
