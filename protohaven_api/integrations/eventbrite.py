"""Facilitates fetching event information from Eventbrite"""

import datetime
import random
import string
from typing import Iterator

from protohaven_api.config import get_config, tznow
from protohaven_api.integrations.data.connector import get as get_connector
from protohaven_api.integrations.models import Event

type EventbriteID = str
type DiscountCode = str


def _eb_timestr(d: datetime.datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def is_valid_id(evt_id: EventbriteID) -> bool:
    """Eventbrite IDs are massive versus Neon IDs; we can use this to determine whether
    an arbitrary event ID is from Eventbrite"""
    return int(evt_id) >= 375402919237


def fetch_events(
    include_ticketing=True, status="live", batching=False
) -> Iterator[Event] | Iterator[list[Event]]:
    """Fetches all events from Eventbrite.
    To view attendee counts etc, set include_ticketing=True
    use "status" to filter results
    See https://www.eventbrite.com/platform/api#/reference/event/list/list-events-by-organization
    """
    url = f"/organizations/{get_config('eventbrite/organization_id')}/events/"
    params = {}
    if status:
        params["status"] = status
    if include_ticketing:
        params["expand"] = "ticket_classes"
    for _ in range(100):
        rep = get_connector().eventbrite_request("GET", url, params=params)
        if batching:
            yield [Event.from_eventbrite_search(data) for data in rep["events"]]
        else:
            for data in rep["events"]:
                yield Event.from_eventbrite_search(data)
        if not rep["pagination"]["has_more_items"]:
            break
        params["continuation"] = rep["pagination"]["continuation"]


def fetch_event(evt_id: EventbriteID) -> Event:
    """Fetch a single event from eventbrite"""
    return Event.from_eventbrite_search(
        get_connector().eventbrite_request(
            "GET", f"/events/{evt_id}", params={"expand": "ticket_classes"}
        )
    )


def generate_discount_code(
    evt_id: EventbriteID, percent_off: int, expiration_hours: int = 1
) -> DiscountCode:
    """Create a discount code for a specific Eventbrite event that expires in 4 hours."""
    now = tznow()
    params = {
        "discount": {
            "type": "coded",
            "event_id": evt_id,
            "code": "".join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            ),
            "percent_off": str(percent_off),
            "currency": "USD",
            "quantity_available": 1,
            "start_date": _eb_timestr(now),
            "end_date": _eb_timestr(now + datetime.timedelta(hours=expiration_hours)),
            "ticket_classes": [],
        }
    }
    url = f"/organizations/{get_config('eventbrite/organization_id')}/discounts/"
    response = get_connector().eventbrite_request("POST", url, params)
    if not response["id"]:
        raise RuntimeError(f"Failed to create eventbrite discount code: {response}")
    return response["id"]
