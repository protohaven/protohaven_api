"""handlers for main landing page"""
import datetime
import json
import logging
import time

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, redirect, request, session
from flask_sock import Sock

from protohaven_api.automation.membership import sign_in
from protohaven_api.config import tz, tznow
from protohaven_api.handlers.auth import user_email, user_fullname
from protohaven_api.integrations import airtable, neon
from protohaven_api.integrations.booked import get_reservations
from protohaven_api.integrations.schedule import fetch_shop_events
from protohaven_api.rbac import is_enabled as rbac_enabled
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
    if not rbac_enabled():
        return {
            "fullname": "Test User (RBAC disabled)",
            "email": "noreply@noreply.com",
            "clearances": [],
            "roles": [],
            "neon_id": "00000",
        }
    if not session.get("neon_account"):
        return Response("You are not logged in", status=400)

    neon_account = session.get("neon_account")
    clearances = []
    roles = []
    for cf in neon_account.get("accountCustomFields", []):
        if cf["name"] == "Clearances":
            clearances = [v["name"] for v in cf["optionValues"]]
        if cf["name"] == "API server role":
            roles = [v["name"] for v in cf["optionValues"]]

    return {
        "fullname": user_fullname(),
        "email": user_email(),
        "neon_id": session.get("neon_id", ""),
        "clearances": clearances,
        "roles": roles,
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
    m = list(neon.search_member(data["email"]))
    if len(m) == 0:
        raise KeyError("Member not found")
    neon.update_announcement_status(m[0]["Account ID"])
    return {"status": "OK"}


@page.route("/welcome/survey_response", methods=["POST"])
def survey_response():
    """Set the acknowledgement date to `now` so prior announcements
    are no longer displayed"""
    data = request.json

    neon_id = None
    m = list(neon.search_member(data["email"]))
    if len(m) != 0:
        neon_id = m[0]["Account ID"]
    status, content = airtable.insert_simple_survey_response(
        data["rec_id"], data["email"], neon_id, data["response"]
    )
    if status != 200:
        log.error(f"Survey response error {status}: {content}")
    return Response(json.dumps({"status": status}), status=status)


@page.route("/class_listing", methods=["GET"])
def class_listing():
    """Returns a list of classes that are upcoming"""
    result = list(neon.fetch_published_upcoming_events(back_days=0))
    sched = {
        str(s["fields"]["Neon ID"]): s
        for s in airtable.get_class_automation_schedule()
        if s["fields"].get("Neon ID")
    }
    for c in result:
        c["timestamp"] = dateparser.parse(
            f"{c['startDate']} {c.get('startTime') or ''}"
        ).astimezone(tz)
        c["day"] = c["timestamp"].strftime("%A, %b %-d")
        c["time"] = c["timestamp"].strftime("%-I:%M %p")
        c["airtable_data"] = sched.get(str(c["id"]))
    result.sort(key=lambda c: c["timestamp"])
    return result


@page.route("/neon_lookup", methods=["POST"])
def neon_id_lookup():
    """Look up the ID of a user in Neon based on a search by name or email"""
    result = []
    search = request.values.get("search")
    if search is None:
        return result
    rep = neon.soft_search(search)
    if not rep.get("success"):
        raise RuntimeError(rep)

    for i in rep["data"]["individuals"]:
        i = i["data"]
        result.append(f"{i['firstName']} {i['lastName']} (#{i['accountId']})")
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
    attendees = 0
    for a in neon.fetch_attendees(event_id):
        if a["registrationStatus"] == "SUCCEEDED":
            attendees += 1
    return str(attendees)


@page.route("/events/upcoming")
def upcoming_events():
    """Show relevant upcoming events."""
    events = []
    now = tznow()

    try:
        instructors_map = {
            str(s["fields"]["Neon ID"]): s["fields"]["Instructor"]
            for s in airtable.get_class_automation_schedule()
            if s["fields"].get("Neon ID")
        }
    except Exception:  # pylint: disable=broad-exception-caught
        log.error("Failed to fetch instructor map, proceeding anyways")
        instructors_map = {}

    for e in neon.fetch_published_upcoming_events():
        if not e.get("startDate"):
            continue
        if e["id"] == 17631:
            continue  # Don't list private instruction
        start = dateparser.parse(
            e["startDate"] + " " + (e.get("startTime") or "")
        ).astimezone(tz)
        end = dateparser.parse(
            e["endDate"] + " " + (e.get("endTime") or "")
        ).astimezone(tz)

        if end < now:
            continue
        events.append(
            {
                "id": e["id"],
                "name": e["name"],
                "date": start,
                "instructor": instructors_map.get(str(e["id"]), ""),
                "start_date": start.strftime("%a %b %d"),
                "start_time": start.strftime("%-I:%M %p"),
                "end_date": end.strftime("%a %b %d"),
                "end_time": end.strftime("%-I:%M %p"),
                "capacity": e["capacity"],
                "registration": e["enableEventRegistrationForm"]
                and start - datetime.timedelta(hours=24) > now,
            }
        )

    events.sort(key=lambda e: e["date"])
    return {"now": now, "events": events}


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
