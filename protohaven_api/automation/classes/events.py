"""Methods for manipulating Eventbrite event data"""

import datetime
from typing import Any, Callable, Iterable, cast

from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, eventbrite
from protohaven_api.integrations.eventbrite import EventbriteID
from protohaven_api.integrations.models import Attendee, Event


def fetch_upcoming_events(
    back_days: int = 7,
    published: bool = True,
    merge_airtable: bool = False,
    attendees: bool | Callable[[Any], bool] = False,
    tickets: bool | Callable[[Any], bool] = False,
) -> Iterable[Event]:
    """Load upcoming Eventbrite events, with `back_days` of trailing event data.

    Note that querying is done based on the end date so multi-week intensives
    can still appear even if they started earlier than `back_days`.

    `tickets` is retained for API compatibility; Eventbrite search results
    already include ticket class data.
    """
    del tickets  # Eventbrite search results include ticket data by default.
    after = tznow() - datetime.timedelta(days=back_days)

    airtable_raw = (
        airtable.get_class_automation_schedule_raw() if merge_airtable else []
    )
    airtable_map = {}
    for s in airtable_raw:
        # Prefer the Eventbrite event ID; fall back to Neon ID for rows
        # that predate the Eventbrite migration.
        evt_id = s["fields"].get("Event ID") or s["fields"].get("Neon ID")
        if evt_id:
            airtable_map[str(evt_id)] = s

    batches = cast(
        Iterable[list[Event]],
        eventbrite.fetch_events(
            status="live,started,ended,completed",
            batching=True,
            attendees=bool(attendees),
        ),
    )
    for batch in batches:
        for evt in batch:
            if not evt or not evt.end_date or evt.end_date < after:
                continue
            if published and not evt.published:
                continue
            evt.set_airtable_data(airtable_map.get(evt.event_id))
            yield evt


def fetch_event(event_id: EventbriteID, tickets=False, attendees=False) -> Event:
    """Fetch event info from Eventbrite"""
    return eventbrite.fetch_event(event_id, include_ticketing=(tickets or attendees))


def fetch_attendees(event_id: EventbriteID) -> Iterable[Attendee]:
    """Fetch attendee info from Eventbrite"""
    yield from eventbrite.fetch_attendees(event_id)


def set_event_scheduled_state(event_id: EventbriteID, scheduled: bool):
    """Set scheduled state on an Eventbrite event"""
    return eventbrite.set_event_scheduled_state(event_id, scheduled=scheduled)
