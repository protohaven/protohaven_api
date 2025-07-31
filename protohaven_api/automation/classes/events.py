"""Methods for manipulating merged event data (from Neon and Airtable)"""

import datetime

from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, eventbrite, neon, neon_base
from protohaven_api.integrations.models import Event


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
        if fetch_attendees:
            evt.set_attendee_data(neon.fetch_attendees(evt.neon_id))
        if fetch_tickets:
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
    if merge_airtable:
        airtable_map = {
            int(s["fields"].get("Neon ID")): s
            for s in airtable.get_class_automation_schedule()
            if s["fields"].get("Neon ID")
        }
    else:
        airtable_map = None

    after = tznow() - datetime.timedelta(days=back_days)
    yield from fetch_upcoming_events_neon(
        after, published, airtable_map, fetch_attendees, fetch_tickets
    )
    for evt in eventbrite.fetch_events(status="live,started,ended,completed"):
        if not evt.end_date or evt.end_date < after:
            continue
        if airtable_map:
            evt.set_airtable_data(airtable_map.get(evt.neon_id))
        yield evt
