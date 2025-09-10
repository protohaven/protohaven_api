"""Facilitates fetching event information from Eventbrite"""

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector
from protohaven_api.integrations.models import Event


def is_valid_id(evt_id):
    """Eventbrite IDs are massive versus Neon IDs; we can use this to determine whether
    an arbitrary event ID is from Eventbrite"""
    return int(evt_id) >= 375402919237


def fetch_events(include_ticketing=True, status="live", batching=False):
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


def fetch_event(evt_id):
    """Fetch a single event from eventbrite"""
    return Event.from_eventbrite_search(
        get_connector().eventbrite_request(
            "GET", f"/events/{evt_id}", params={"expand": "ticket_classes"}
        )
    )
