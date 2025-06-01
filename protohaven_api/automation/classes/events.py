""" Methods for manipulating merged event data (from Neon and Airtable) """

import datetime

from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, neon, neon_base
from protohaven_api.integrations.models import Event


def fetch_upcoming_events(
    back_days=7,
    published=True,
    merge_airtable=False,
    fetch_attendees=False,
    fetch_tickets=False,
):
    """Load upcoming events from Neon CRM, with `back_days` of trailing event data.
    Note that querying is done based on the end date so multi-week intensives
    can still appear even if they started earlier than `back_days`."""
    q_params = {
        "endDateAfter": (tznow() - datetime.timedelta(days=back_days)).strftime(
            "%Y-%m-%d"
        ),
        "archived": False,
    }
    if published:
        q_params["publishedEvent"] = published

    if merge_airtable:
        airtable_map = {
            int(s["fields"].get("Neon ID")): s
            for s in airtable.get_class_automation_schedule()
        }
    else:
        airtable_map = None

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
