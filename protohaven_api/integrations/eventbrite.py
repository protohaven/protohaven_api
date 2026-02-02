"""Facilitates fetching event information from Eventbrite"""

import datetime
import logging
import random
import string
from io import BytesIO
from typing import Iterator

import requests

from protohaven_api.config import get_config, tznow
from protohaven_api.integrations.airtable import Interval
from protohaven_api.integrations.data.connector import get as get_connector
from protohaven_api.integrations.models import Event

type EventbriteID = str
type DiscountCode = str

log = logging.getLogger("protohaven_api.integrations.eventbrite")


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


def fetch_event(evt_id: EventbriteID, include_ticketing=False) -> Event:
    """Fetch a single event from eventbrite"""
    params = {}
    if include_ticketing:
        params["expand"] = "ticket_classes"
    return Event.from_eventbrite_search(
        get_connector().eventbrite_request("GET", f"/events/{evt_id}", params=params)
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


def _utcfmt(d: datetime.datetime) -> str:
    return (
        d.astimezone(datetime.timezone.utc).isoformat(timespec="seconds").split("+")[0]
        + "Z"
    )


def create_event(  # pylint: disable=too-many-arguments
    name: str,
    sessions: list[Interval],
    max_attendees: int = 6,
    published: bool = True,
    logo_id: int | None = None,
) -> EventbriteID:
    """Create an event in Eventbrite, possibly creating an Event Series if there are
    multiple sessions."""
    params = {
        "event": {
            "name": {
                "html": name
                + ("" if len(sessions) <= 1 else f" ({len(sessions)} sessions)"),
            },
            "start": {
                "timezone": "America/New_York",
                "utc": _utcfmt(sessions[0][0]),
            },
            "end": {
                "timezone": "America/New_York",
                "utc": _utcfmt(sessions[-1][1]),
            },
            # Venues are separate entities stored on Eventbrite server. This assumes
            # we're always hosting at Protohaven
            # https://www.eventbrite.com/platform/api#/reference/venue/list/list-venues-by-organization?console=1
            "venue_id": "103409419",
            "currency": "USD",
            "listed": published,
            "show_remaining": True,
            "capacity": max_attendees,
            "logo_id": logo_id,
            # "is_series": len(sessions) > 1,
        }
    }
    url = f"/organizations/{get_config('eventbrite/organization_id')}/events/"
    response = get_connector().eventbrite_request("POST", url, json=params)
    event_id = response.get("id") or None
    if not event_id:
        raise RuntimeError(f"Failed to create eventbrite event: {response}")

    # for t0, t1 in sessions[1:]:
    #     # We create a separate schedule for each session, as Eventbrite's setup requires
    #     # every event in the schedule to have the same duration
    #     url = f"/events/{event_id}/schedules/"

    #     # Eventbrite expects ISO8601 without punctuation and no timezone offset
    #     startstr = _utcfmt(t0).replace('-', '').replace(':','')
    #     params = {
    #         "schedule": {
    #             "occurrence_duration": round((t1 - t0).total_seconds()),
    #             "recurrence_rule": f"DTSTART:{startstr}\nRRULE:FREQ=DAILY;COUNT=1",
    #         }
    #     }
    #     response = get_connector().eventbrite_request("POST", url, json=params)
    #     if not response.get("id"):
    #         raise RuntimeError(
    #             f"Failed to set session for eventbrite event {event_id}: {response}"
    #         )

    return event_id


def set_structured_content(event_id: EventbriteID, desc: str, content_version=2):
    """Sets the structured content (Overview) of the event.

    Note: `content_version` is an incremental ID at the event level.
    ID 1 is apparently already taken.

    If setting contenton an existing event, the content_version will
    need to be incremented.
    """
    content = {
        "access_type": "public",
        "modules": [
            {
                "data": {
                    "body": {
                        "alignment": "left",
                        # Note: this field is HTML aware, but filters out
                        # non-text elements (e.g. img tags)
                        "text": desc,
                    }
                },
                "layout": "image_left",
                "type": "text",
            }
        ],
        "purpose": "listing",
    }
    response = get_connector().eventbrite_request(
        "POST",
        f"/events/{event_id}/structured_content/{content_version}/",
        json=content,
    )
    if not response.get("page_version_number"):
        raise RuntimeError(
            f"Failed to set structured content for eventbrite event {event_id}: {response}"
        )
    return content_version


def assign_pricing(event_id: EventbriteID, price: int, seats: int):
    """Creates a ticket class attached to `event_id`.
    Note that discounts are instantly generated on redirect via /member/goto_class.
    """
    params = {
        "ticket_class": {
            "quantity_total": seats,
            "cost": f"USD,{round(price*100)}" if price != 0 else None,
            "free": (price == 0),
            "name": "General Admission",
            "sales_end_relative": {
                "relative_to_event": "start_time",
                "offset": 3600 * 24,
            },
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


def upload_logo_image(image_url: str):
    """Sets the logo of the event to an image from a URL.
    See https://www.eventbrite.com/platform/docs/image-upload.

    Behind the scenes, this uploads to an S3 bucket owned by Eventbrite."""

    img = requests.get(image_url, timeout=30)
    img.raise_for_status()
    content_type = img.headers.get("Content-Type", "image/jpeg")
    file_extension = content_type.split("/")[-1]

    # First request to fetch the upload token
    prep = get_connector().eventbrite_request(
        "GET", "/media/upload/?type=image-event-logo"
    )

    # Second request to upload the image (probably Amazon S3)
    response = requests.post(
        prep["upload_url"],
        data=prep["upload_data"],
        files={
            prep["file_parameter_name"]: (
                f"image.{file_extension}",
                BytesIO(img.content),
                content_type,
            ),
        },
        timeout=get_config("connector/timeout"),
    )
    response.raise_for_status()

    # Final request to notify successful save
    confirm_rep = get_connector().eventbrite_request(
        "POST",
        "/media/upload/",
        json={
            "upload_token": prep["upload_token"],
            "crop_mask": {"top_left": {"y": 1, "x": 1}, "width": 1280, "height": 640},
        },
    )
    if not confirm_rep.get("id"):
        raise RuntimeError(f"Failed to confirm image upload to Eventbrite: {response}")

    return confirm_rep.get("id")
