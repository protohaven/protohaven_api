"""Methods for manipulating merged event data (from Neon and Airtable)"""

import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, eventbrite, neon, neon_base
from protohaven_api.integrations.models import Event


def _should(condition: bool | Callable[[Any], bool], v: Any) -> bool:
    """Evaluates a boolean or a function which returns a boolean. This
    enables selective fetching of supplemental data per-record"""
    if callable(condition):
        return condition(v)
    if isinstance(condition, bool):
        return condition
    return False


def fetch_upcoming_events_neon(
    after,
    published=True,
    airtable_map=None,
    fetch_attendees=False,
    fetch_tickets=False,
):
    """Fetch only neon upcoming events"""
    q_params = {
        "endDateAfter": after.strftime("%Y-%m-%d"),
        "archived": False,
    }
    if published:
        q_params["publishedEvent"] = published

    for e in neon_base.paginated_fetch("api_key1", "/events", q_params):
        evt = Event.from_neon_fetch(e)
        if airtable_map:
            evt.set_airtable_data(airtable_map.get(evt.neon_id))
        if _should(fetch_attendees, evt):
            evt.set_attendee_data(neon.fetch_attendees(evt.neon_id))
        if _should(fetch_tickets, evt):
            evt.set_ticket_data(
                neon.fetch_tickets_internal_do_not_use_directly(evt.neon_id)
            )
        yield evt


def fetch_upcoming_events(
    back_days=7,
    published=True,
    merge_airtable=False,
    fetch_attendees=False,
    fetch_tickets=False,
):
    """Load upcoming events from all sources, with `back_days` of trailing event data.
    Note that querying is done based on the end date so multi-week intensives
    can still appear even if they started earlier than `back_days`."""
    with ThreadPoolExecutor() as executor:
        airtable_map = None
        airtable_future = (
            executor.submit(airtable.get_class_automation_schedule)
            if merge_airtable
            else None
        )

        after = tznow() - datetime.timedelta(days=back_days)
        neon_future = executor.submit(
            fetch_upcoming_events_neon,
            after,
            published,
            airtable_map,
            fetch_attendees,
            fetch_tickets,
        )

        eb_future = executor.submit(
            eventbrite.fetch_events, status="live,started,ended,completed"
        )

        airtable_raw = airtable_future.result() if airtable_future is not None else []
        neon_raw = neon_future.result()
        eb_raw = eb_future.result()

    if merge_airtable:
        airtable_map = {
            int(s["fields"].get("Neon ID")): s
            for s in airtable_raw
            if s["fields"].get("Neon ID")
        }

    yield from neon_raw
    for evt in eb_raw:
        if not evt.end_date or evt.end_date < after:
            continue
        if airtable_map:
            evt.set_airtable_data(airtable_map.get(evt.neon_id))
        yield evt
