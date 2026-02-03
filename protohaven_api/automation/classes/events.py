"""Methods for manipulating merged event data (from Neon and Airtable)"""

import datetime
from concurrent import futures
from functools import partial
from typing import Any, Callable, Iterable

from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, eventbrite, neon, neon_base
from protohaven_api.integrations.airtable import NeonID
from protohaven_api.integrations.eventbrite import EventbriteID
from protohaven_api.integrations.models import Attendee, Event


def _should(condition: bool | Callable[[Any], bool], v: Any) -> bool:
    """Evaluates a boolean or a function which returns a boolean. This
    enables selective fetching of supplemental data per-record"""
    if callable(condition):
        return condition(v)
    if isinstance(condition, bool):
        return condition
    return False


def _fetch_upcoming_events_neon(
    after: datetime.datetime,
    published: bool = True,
    attendees: bool = False,
    tickets: bool = False,
) -> Iterable[list[Event]]:
    """Fetch only neon upcoming events"""
    q_params = {
        "endDateAfter": after.strftime("%Y-%m-%d"),
        "archived": False,
    }
    if published:
        q_params["publishedEvent"] = published

    for ee in neon_base.paginated_fetch("api_key1", "/events", q_params, batching=True):
        batch = []
        for e in ee:
            evt = Event.from_neon_fetch(e)
            if _should(attendees, evt):
                evt.set_attendee_data(neon.fetch_attendees(evt.neon_id))
            if _should(tickets, evt):
                evt.set_ticket_data(
                    # Specifically allowed to do so here; others should
                    # Use `fetch_upcoming_events` to get ticket data
                    neon.fetch_tickets_internal_do_not_use_directly(evt.neon_id)
                )
            batch.append(evt)
        yield batch


def fetch_upcoming_events(  # pylint: disable=too-many-locals
    back_days: int = 7,
    published: bool = True,
    merge_airtable: bool = False,
    attendees: bool = False,
    tickets: bool = False,
) -> Iterable[Event]:
    """Load upcoming events from all sources, with `back_days` of trailing event data.
    Note that querying is done based on the end date so multi-week intensives
    can still appear even if they started earlier than `back_days`."""
    after = tznow() - datetime.timedelta(days=back_days)

    with futures.ThreadPoolExecutor() as executor:
        airtable_future = (
            executor.submit(airtable.get_class_automation_schedule)
            if merge_airtable
            else None
        )
        neon_gen = _fetch_upcoming_events_neon(after, published, attendees, tickets)
        eb_gen = eventbrite.fetch_events(
            status="live,started,ended,completed", batching=True
        )
        not_done: set[futures.Future] = {
            executor.submit(lambda: (neon_gen, next(neon_gen))),
            executor.submit(lambda: (eb_gen, next(eb_gen))),
        }

        # We need airtable data first so we can annotate
        airtable_raw = airtable_future.result() if airtable_future is not None else []
        airtable_map = {
            int(s["fields"].get("Neon ID")): s
            for s in airtable_raw
            if s["fields"].get("Neon ID")
        }

        # Since our event fetches are both paginated generators,
        # we have to submit them to the thread pool multiple times to
        # maintain asynchronous results
        while True:
            done: set[futures.Future] = set()
            done, not_done = futures.wait(not_done, return_when=futures.FIRST_COMPLETED)
            for d in done:
                try:
                    gen, result = d.result()
                    # We use `partial` here to store the value of `gen`
                    # so that it isn't updated out from under the executor
                    # job due to reassignment in the for loop
                    next_gen = partial(lambda g: (g, next(g)), gen)
                    not_done.add(executor.submit(next_gen))
                except StopIteration:
                    continue

                for evt in result:
                    if not evt or not evt.end_date or evt.end_date < after:
                        continue
                    evt.set_airtable_data(airtable_map.get(evt.neon_id))
                    yield evt

            if len(not_done) <= 0:
                break


def fetch_event(
    event_id: EventbriteID | NeonID, tickets=False, attendees=False
) -> Event:
    """Compatibility method to fetch event info from Neon or Eventbrite"""
    if eventbrite.is_valid_id(event_id):
        return eventbrite.fetch_event(
            event_id, include_ticketing=(tickets or attendees)
        )
    return neon.fetch_event(event_id, tickets=tickets, attendees=attendees)


def fetch_attendees(event_id: EventbriteID | NeonID) -> list[Attendee]:
    """Compatibility method to fetch attendee info from Neon or Eventbrite"""
    if eventbrite.is_valid_id(event_id):
        yield from eventbrite.fetch_attendees(event_id)
    else:
        yield from neon.fetch_attendees(event_id)


def set_event_scheduled_state(event_id: EventbriteID | NeonID, scheduled: bool):
    """Compatibility method to set scheduled state on Neon or Eventbrite event"""
    if eventbrite.is_valid_id(event_id):
        return eventbrite.set_event_scheduled_state(event_id, scheduled=scheduled)
    return neon.set_event_scheduled_state(event_id, scheduled=scheduled)
