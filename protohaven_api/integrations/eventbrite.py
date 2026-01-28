"""Facilitates fetching event information from Eventbrite"""

import datetime
import random
import string
from typing import Iterator

from protohaven_api.config import get_config, tznow
from protohaven_api.integrations.airtable import Interval
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
    response = get_connector().eventbrite_request("POST", url, json=params)
    if not response["id"]:
        raise RuntimeError(f"Failed to create eventbrite discount code: {response}")
    return response["id"]


def create_event(  # pylint: disable=too-many-arguments
    name: str,
    desc: str,
    sessions: list[Interval],
    max_attendees: int = 6,
    published: bool = True,
) -> EventbriteID:
    """Create an event in Eventbrite, possibly creating an Event Series if there are
    multiple sessions."""
    params = {
        "event": {
            "name": {
                "text": name,
            },
            "description": {
                "html": desc,
            },
            "start": {
                "timezone": "UTC",
                "utc": sessions[0][0].astimezone(datetime.timezone.utc).isoformat(),
            },
            "end": {
                "timezone": "UTC",
                "utc": sessions[-1][1].astimezone(datetime.timezone.utc).isoformat(),
            },
            "currency": "USD",
            "listed": published,
            "show_remaining": True,
            "capacity": max_attendees,
            "is_series": len(sessions) > 1,
        }
    }
    url = f"/organiations/{get_config('eventbrite/organization_id')}/events"
    response = get_connector().eventbrite_request("POST", url, json=params)
    event_id = response.get("id") or None
    if not event_id:
        raise RuntimeError(f"Failed to create eventbrite event: {response}")

    for t0, t1 in sessions[1:]:
        # We create a separate schedule for each session, as Eventbrite's setup requires
        # every event in the schedule to have the same duration
        url = f"/events/{event_id}/schedules/"
        startstr = (
            t0.astimezone(datetime.timezone.utc)
            .isoformat()
            .replace("-", "")
            .replace(":", "")
        )
        params = {
            "schedule": {
                "occurrence_duration": (t1 - t0).total_seconds(),
                "recurrence_rule": f"DTSTART:{startstr}",
            }
        }
        response = get_connector().eventbrite_request("POST", url, json=params)
        if not response.get("id"):
            raise RuntimeError(
                f"Failed to set session for eventbrite event {event_id}: {response}"
            )

    return event_id


def assign_pricing(
    event_id: EventbriteID, price: int, seats: int, sale_closes: datetime.datetime
):
    """Creates a ticket class attached to `event_id`.
    Note that discounts are instantly generated on redirect via /member/goto_class.
    """
    params = {
        "ticket_class": {
            "maximum_quantity": seats,
            "cost": f"USD,{price*100}",
            "display_name": "General Admission",
            "quantity_sold": 0,
            "sales_start": "",
            "sales_end": sale_closes.astimezone(datetime.timezone.utc).isoformat(),
            "hide_sale_dates": True,
        }
    }
    url = f"/events/{event_id}/ticket_classes/"
    response = get_connector().eventbrite_request("POST", url, json=params)
    if not response["resource_uri"]:
        raise RuntimeError(f"Failed to create eventbrite ticket class: {response}")
    return response["resource_uri"]


def delete_event_unsafe(event_id: EventbriteID):
    """Deletes an event in Eventbrite.

    Note that per the API reference,
    "To delete an Event, the Event must not have any pending or completed orders."
    """
    url = f"/events/{event_id}"
    return get_connector().eventbrite_request("DELETE", url)


def set_event_scheduled_state(event_id: EventbriteID, scheduled: bool = True):
    """Sets the scheduled state of the event in Eventbrite. Note that eventbrite restricts
    destructive actions (including unpublishing) on events that have completed orders.
    """
    if scheduled:
        url = f"/events/{event_id}/publish/"
        response = get_connector().eventbrite_request("POST", url)
        if not response.get("published"):
            raise RuntimeError(f"Failed to publish event {event_id}: {response}")
        return response

    # Deschedule/unpublish option
    url = f"/events/{event_id}/unpublish/"
    response = get_connector().eventbrite_request("POST", url)
    if not response.get("unpublished"):
        raise RuntimeError(f"Failed to unpublish event {event_id}: {response}")
    return response
