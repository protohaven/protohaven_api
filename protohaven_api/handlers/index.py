"""handlers for main landing page"""
import datetime
import json

from dateutil import parser as dateparser
from flask import Blueprint, Response, current_app, render_template, request, session

from protohaven_api.config import tz, tznow
from protohaven_api.handlers.auth import user_email, user_fullname
from protohaven_api.integrations import airtable, neon
from protohaven_api.integrations.booked import get_reservations
from protohaven_api.integrations.forms import submit_google_form
from protohaven_api.integrations.schedule import fetch_shop_events
from protohaven_api.rbac import require_login

page = Blueprint("index", __name__, template_folder="templates")


@page.route("/")
@require_login
def index():
    """Show the main dashboard page"""
    neon_account = session.get("neon_account")
    clearances = []
    roles = []
    neon_account["custom_fields"] = {"Clearances": {"optionValues": []}}
    neon_json = json.dumps(neon_account, indent=2)
    for cf in neon_account["individualAccount"]["accountCustomFields"]:
        if cf["name"] == "Clearances":
            clearances = [v["name"] for v in cf["optionValues"]]
        if cf["name"] == "API server role":
            roles = [v["name"] for v in cf["optionValues"]]
        neon_account["custom_fields"][cf["name"]] = cf

    return render_template(
        "dashboard.html",
        fullname=user_fullname(),
        email=user_email(),
        neon_id=session.get("neon_id"),
        neon_account=neon_account,
        neon_json=neon_json,
        clearances=clearances,
        roles=roles,
    )


@page.route("/whoami")
def whoami():
    """Returns data about the logged in user"""
    if not session.get("neon_account"):
        return Response("You are not logged in", status=400)
    return {"fullname": user_fullname(), "email": user_email()}


@page.route("/welcome/_app/immutable/<typ>/<path>")
def welcome_svelte_files(typ, path):
    """Return svelte compiled static pages for welcome page"""
    return current_app.send_static_file(f"svelte/_app/immutable/{typ}/{path}")


@page.route("/logo_color.svg")
def welcome_logo():
    """Return svelte compiled static pages for welcome page"""
    return current_app.send_static_file("svelte/logo_color.svg")


@page.route("/welcome", methods=["GET", "POST"])
def welcome_signin():
    """Sign-in page at front desk"""
    if request.method == "GET":
        return current_app.send_static_file("svelte/index.html")

    if request.method == "POST":
        result = {
            "notfound": False,
            "status": False,
            "waiver_signed": False,
            "announcements": [],
            "firstname": "member",
        }
        data = request.json
        if data["person"] == "member":
            m = neon.search_member(data["email"])
            print(m)
            if not m:
                result["notfound"] = True
            else:
                result["status"] = m.get("Account Current Membership Status", "Unknown")
                result["firstname"] = m.get("First Name")
                last_announcement_ack = m.get("Announcements Acknowledged", None)
                if last_announcement_ack:
                    last_announcement_ack = dateparser.parse(
                        last_announcement_ack
                    ).astimezone(tz)
                else:
                    last_announcement_ack = tznow() - datetime.timedelta(30)
                roles = [
                    r
                    for r in (m.get("API server role", "") or "").split(
                        "|"
                    )  # Can be None
                    if r.strip() != ""
                ]
                if result["status"] == "Active":
                    roles.append("Member")
                result["announcements"] = airtable.get_announcements_after(
                    last_announcement_ack, roles
                )

                result["waiver_signed"] = neon.update_waiver_status(
                    m["Account ID"],
                    m.get("Waiver Accepted"),
                    data.get("waiver_ack", False),
                )
        elif data["person"] == "guest":
            result["waiver_signed"] = data.get("waiver_ack", False)
            result["firstname"] = "Guest"

        if (
            data["person"] == "member"
            and result["notfound"] is False
            and result["waiver_signed"]
        ) or (data["person"] == "guest" and data.get("referrer")):
            # Note: setting `purpose` this way tricks the form into not requiring other fields
            assert result["waiver_signed"] is True
            form_data = {
                "email": data["email"],
                "dependent_info": data["dependent_info"],
                "waiver_ack": (
                    "I have read and understand this agreement and "
                    "agree to be bound by its requirements.",  # Must be this, otherwise 400 error
                ),
                "referrer": data.get("referrer"),
                "purpose": "I'm a member, just signing in!",
                "am_member": "Yes" if data["person"] == "member" else "No",
            }
            rep = submit_google_form("signin", form_data)
            print(rep.request.url)
            print("Google form submitted, response", rep)
        return result

    return ""


@page.route("/welcome/announcement_ack", methods=["POST"])
def acknowledge_announcements():
    """Set the acknowledgement date to `now` so prior announcements
    are no longer displayed"""
    data = request.json
    m = neon.search_member(data["email"])
    if not m:
        raise KeyError("Member not found")
    resp, _ = neon.update_announcement_status(m["Account ID"])
    if resp.status != 200:
        raise RuntimeError("Failed to update announcement acknowledgement")
    return "OK"


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


@page.route("/neon_lookup", methods=["GET", "POST"])
def neon_id_lookup():
    """Look up the ID of a user in Neon based on a search by name or email"""
    if request.method == "GET":
        return render_template("search.html")

    # invariant: request.method == "POST"
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


@page.route("/events")
def events_dashboard():
    """Show relevant upcoming events - designed for a kiosk display"""
    events = []
    now = tznow()
    # NOTE: does not currently support intensive date periods. Need to expand
    # dates to properly show this.
    try:
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

            # Only include events that haven't ended
            if end < now:
                continue
            events.append(
                {
                    "id": e["id"],
                    "name": e["name"],
                    "date": start,
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
    except json.decoder.JSONDecodeError:
        print("Neon error, proceeding anyways")

    shop_events = []
    for e, dates in fetch_shop_events().items():
        for start, end in dates:
            start = dateparser.parse(start)
            shop_events.append((e, start))
    shop_events.sort(key=lambda v: v[1])

    reservations = []
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
    print(reservations)
    now = tznow()
    return render_template(
        "events.html",
        events=events,
        shop_events=shop_events,
        reservations=reservations,
        now=now,
        hide_events_after=now + datetime.timedelta(days=7),
    )
