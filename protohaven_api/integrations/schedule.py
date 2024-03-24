"""Calendar fetching methods.

Requires access to be granted: https://calendar.google.com/calendar/u/0/embed?src=c_ab048e21805a0b5f7f094a81f6dbd19a3cba5565b408962565679cd48ffd02d9@group.calendar.google.com&ctz=America/New_York          #pylint: disable=line-too-long
"""
import logging
import os.path
from collections import defaultdict
from datetime import datetime, timedelta

from dateutil import parser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from protohaven_api.config import get_config

cfg = get_config()["calendar"]

log = logging.getLogger("integrations.schedule")

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def fetch_calendar(calendar_id, time_min=None, time_max=None):
    """Fetches calendar data - default to next 30 days"""

    if time_min is None:
        time_min = datetime.utcnow()
    if time_max is None:
        time_max = datetime.utcnow() + timedelta(days=30)
    time_min = time_min.isoformat() + "Z"  # 'Z' indicates UTC time
    time_max = time_max.isoformat() + "Z"  # 'Z' indicates UTC time

    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)
    # Call the Calendar API
    log.info(f"querying calendar {calendar_id}: {time_min} to {time_max}")
    events_result = (
        service.events()  # pylint: disable=no-member
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=10000,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])
    if not events:
        raise RuntimeError("No upcoming events found.")
    # Bin by event (aka instructor) name
    output = defaultdict(list)
    for event in events:
        if not event.get("summary"):
            log.warning(
                f"Ignoring calendar event missing a title on {event['start'].get('date')}"
            )
            continue
        name = event["summary"]
        start = parser.parse(
            event["start"].get("dateTime", event["start"].get("date"))
        ).isoformat()
        end = parser.parse(
            event["end"].get("dateTime", event["end"].get("date"))
        ).isoformat()
        output[name].append([start, end])

    return output


def fetch_instructor_schedules(time_min, time_max):
    """Fetches instructor-provided availability from the google calendar"""
    return fetch_calendar(cfg["instructor_schedules"], time_min, time_max)


def fetch_shop_events():
    """Fetches onboardings, tours etc. happening in the shop"""
    return fetch_calendar(cfg["shop_events"])
