"""handlers for main landing page"""

import datetime
import json
import logging
import time

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, redirect, request, session
from flask_sock import Sock

from protohaven_api.automation.classes import events as eauto
from protohaven_api.automation.membership import sign_in
from protohaven_api.config import tz, tznow
from protohaven_api.integrations import airtable, eventbrite, mqtt, neon
from protohaven_api.integrations.booked import get_reservations
from protohaven_api.integrations.models import Member
from protohaven_api.integrations.schedule import fetch_shop_events
from protohaven_api.rbac import require_login

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
        "roles": [v["name"] for v in acct.roles],
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


def setup_sock_routes(app):
    """Set up all websocket routes; called by main.py"""
    sock = Sock(app)
    sock.route("/welcome/ws")(welcome_sock)


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
                "id": evt.neon_id,
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


@page.route("/neon_lookup", methods=["POST"])
def neon_id_lookup():
    """Look up the ID of a user in Neon based on a search by name or email"""
    result = []
    search = request.values.get("search")
    if search is None:
        return result
    for i in neon.cache.find_best_match(search):
        result.append(f"{i.fname} {i.lname} (#{i.neon_id})")
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
    if eventbrite.is_valid_id(event_id):
        evt = eventbrite.fetch_event(event_id)
        if evt:
            return str(evt.attendee_count)
    attendees = 0
    for a in neon.fetch_attendees(event_id):
        if a["registrationStatus"] == "SUCCEEDED":
            attendees += 1
    return str(attendees)


@page.route("/events/tickets")
def event_ticket_info():
    """Gets the attendee count for a given event, by its neon ID"""
    event_id = request.args.get("id")
    if event_id is None:
        raise RuntimeError("Requires param id")
    if eventbrite.is_valid_id(event_id):
        evt = eventbrite.fetch_event(event_id)
    else:
        evt = neon.fetch_event(event_id, fetch_tickets=True)
    tickets = []
    for t in evt.ticket_options:
        # While this is technically a no-op, it's a reminder that this response
        # format is expected to have exactly these fields when fetched from the
        # protohaven-events wordpress plugin.
        tickets.append({k: t[k] for k in ("id", "name", "price", "total", "sold")})
    return tickets


@page.route("/events/upcoming")
def upcoming_events():
    """Show relevant upcoming events."""
    events = []
    now = tznow()
    for evt in eauto.fetch_upcoming_events(merge_airtable=True):
        # Don't list private instruction, expired classes,
        # or classes without dates
        log.info(str(evt.end_date))
        if not evt.start_date or evt.in_blocklist() or evt.end_date < now:
            continue
        events.append(
            {
                "id": evt.neon_id,
                "name": evt.name,
                "description": evt.description,
                "instructor": evt.instructor_name,
                "start": evt.start_date.isoformat(),
                "end": evt.end_date.isoformat(),
                "capacity": evt.capacity,
                "url": evt.url,
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
            start = dateparser.parse(start)
            shop_events.append({"name": e, "start": start})
    shop_events.sort(key=lambda v: v["start"])
    return shop_events


@page.route("/events/reservations")
def get_event_reservations():
    """Show reservations."""
    reservations = []
    now = tznow()
    for r in get_reservations(
        now.replace(hour=0, minute=0, second=0),
        now.replace(hour=23, minute=59, second=59),
    )["reservations"]:
        start = dateparser.parse(r["startDate"]).astimezone(tz)
        end = dateparser.parse(r["endDate"]).astimezone(tz)
        open_time = now.replace(hour=10)
        close_time = now.replace(hour=22)
        reservations.append(
            {
                "start": start.strftime("%-I:%M %p") if start > open_time else "open",
                "end": end.strftime("%-I:%M %p") if start < close_time else "close",
                "name": f"{r['firstName']} {r['lastName']}",
                "resource": r["resourceName"],
            }
        )
    return reservations
