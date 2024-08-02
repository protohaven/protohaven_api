# pylint: skip-file
import logging
import re
from collections import namedtuple

from dateutil import parser
from dateutil.rrule import rrulestr
from google.oauth2 import service_account
from googleapiclient.discovery import build

from protohaven_api.config import get_config
from protohaven_api.integrations import airtable
from protohaven_api.integrations.data.connector import init as init_connector

init_connector(False)  # prod

log = logging.getLogger("scripts.transfer_gcal_to_airtable")


cfg = get_config()["calendar"]


def fetch_calendar(calendar_id, time_min=None, time_max=None):
    """Fetches calendar data - default to next 30 days"""
    if time_min is None:
        time_min = datetime.utcnow()
    if time_max is None:
        time_max = datetime.utcnow() + timedelta(days=30)
    time_min = time_min.isoformat() + "Z"  # 'Z' indicates UTC time
    time_max = time_max.isoformat() + "Z"  # 'Z' indicates UTC time

    creds = service_account.Credentials.from_service_account_file(
        "credentials.json", scopes=cfg["scopes"]
    )
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
            singleEvents=False,
        )
        .execute()
    )
    events = events_result.get("items", [])
    if not events:
        raise RuntimeError("No upcoming events found.")
    return events


def get_all_gcal_events():
    return fetch_calendar(
        cfg["instructor_schedules"],
        parser.parse("2024-06-30"),
        parser.parse("2025-01-01"),
    )


def fetch_instructor_name_to_id_mapping():
    """Fetches map of name to ID"""
    result = {}
    for row in airtable.get_all_records("class_automation", "capabilities"):
        result[row["fields"].get("Instructor").strip().lower()] = row["id"]
    return result


if __name__ == "__main__":
    inst_map = fetch_instructor_name_to_id_mapping()
    print("inst_map", inst_map)
    for event in get_all_gcal_events():
        if not event.get("summary"):  # Ignore unnamed events
            continue
        name = event["summary"]
        inst_id = inst_map.get(name.strip().lower())
        if not inst_id:
            raise Exception(f"Failed to match event {event}")

        if not event.get("start") or not event.get("end"):
            raise Exception(f"Weird event {event}")
        start = parser.parse(event["start"].get("dateTime", event["start"].get("date")))
        end = parser.parse(event["end"].get("dateTime", event["end"].get("date")))
        for rrule in event.get("recurrence", [None]):
            print(inst_id, start, end, rrule)
            print(airtable.add_availability(inst_id, start, end, rrule or ""))
