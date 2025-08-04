"""Calendar fetching methods.

Requires access to be granted: https://calendar.google.com/calendar/u/0/embed?src=c_ab048e21805a0b5f7f094a81f6dbd19a3cba5565b408962565679cd48ffd02d9@group.calendar.google.com&ctz=America/New_York          #pylint: disable=line-too-long
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from protohaven_api.config import get_config, safe_parse_datetime
from protohaven_api.integrations.data.connector import get as get_connector

log = logging.getLogger("integrations.schedule")


def fetch_calendar(calendar_id, time_min=None, time_max=None):
    """Fetches calendar data - default to next 30 days"""
    if time_min is None:
        time_min = datetime.utcnow()
    if time_max is None:
        time_max = datetime.utcnow() + timedelta(days=30)
    events_result = get_connector().gcal_request(calendar_id, time_min, time_max)
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
        start = safe_parse_datetime(
            event["start"].get("dateTime", event["start"].get("date"))
        ).isoformat()
        end = safe_parse_datetime(
            event["end"].get("dateTime", event["end"].get("date"))
        ).isoformat()
        output[name].append([start, end])

    return output


def fetch_shop_events():
    """Fetches tours etc. happening in the shop"""
    return fetch_calendar(get_config("calendar/shop_events"))
