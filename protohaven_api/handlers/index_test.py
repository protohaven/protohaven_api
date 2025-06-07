"""Verify proper behavior of public access pages"""
# pylint: skip-file
import json

import pytest

from protohaven_api.app import configure_app
from protohaven_api.handlers import index
from protohaven_api.integrations import neon
from protohaven_api.rbac import set_rbac
from protohaven_api.testing import MatchStr, d, fixture_client, setup_session


def test_index(client):
    """Test behavior of index page"""
    setup_session(client)
    response = client.get("/")
    assert response.status_code == 302
    assert response.location == "/member"


def test_whoami(client):
    """test /whoami returns session info"""
    setup_session(client)
    response = client.get("/whoami")
    assert json.loads(response.data.decode("utf8")) == {
        "fullname": "First Last",
        "email": "foo@bar.com",
        "neon_id": 1234,
        "clearances": ["C1", "C2"],
        "roles": ["Board Member"],
    }


def test_class_listing(mocker, client):
    """Test class_listing function returns sorted class list with airtable data"""
    m1 = mocker.MagicMock(
        neon_id=1, start_date=d(0, 10), description="foo", airtable_data="bar"
    )
    m1.name = "m1"
    m2 = mocker.MagicMock(
        neon_id=2, start_date=d(0, 9), description="foo", airtable_data="baz"
    )
    m2.name = "m2"
    mocker.patch.object(index.eauto, "fetch_upcoming_events", return_value=[m1, m2])
    rep = client.get("/class_listing")
    assert json.loads(rep.data.decode("utf8")) == [
        {
            "id": 2,
            "name": "m2",
            "description": "foo",
            "timestamp": d(0, 9).isoformat(),
            "day": "Wednesday, Jan 1",
            "time": "9:00 AM",
            "airtable_data": "baz",
        },
        {
            "id": 1,
            "name": "m1",
            "description": "foo",
            "timestamp": d(0, 10).isoformat(),
            "day": "Wednesday, Jan 1",
            "time": "10:00 AM",
            "airtable_data": "bar",
        },
    ]


def test_event_tickets_formatting_expected_by_wordpress(mocker, client):
    """This is a separate test specifically to point out that our wordpress
    (protohaven.org/classes/) is actively using this flask handler, and that
    the JSON format MUST match or else we'll end up breaking class browsing
    for people trying to sign up for events."""
    mock_eb_event = mocker.MagicMock(
        ticket_options=[
            {
                "id": "eb123",
                "name": "Eventbrite Event",
                "price": 5.0,
                "total": 8,
                "sold": 3,
            }
        ]
    )
    mocker.patch.object(index.eventbrite, "is_valid_id", return_value=True)
    mocker.patch.object(index.eventbrite, "fetch_event", return_value=mock_eb_event)
    rep = json.loads(client.get("/events/tickets?id=eb123").data.decode("utf8"))
    assert isinstance(rep, list)
    for k in ("id", "name", "price", "total", "sold"):
        assert k in rep[0]


def test_upcoming_events_formatting_expected_by_wordpress(mocker, client):
    """This is a separate test specifically to point out that our wordpress
    (protohaven.org/classes/) is actively using this flask handler, and that
    the JSON format MUST match or else we'll end up breaking class browsing
    for people trying to sign up for events.

    See also test_event_tickets_formatting_expected_by_wordpress
    """
    mocker.patch.object(index, "tznow", return_value=d(0))
    mock_event = mocker.Mock(
        neon_id="123",
        description="Test Description",
        instructor_name="Instructor",
        start_date=d(1, 16),
        end_date=d(1, 19),
        capacity=10,
        url="http://example.com",
        registration=True,
        in_blocklist=False,
    )
    mocker.patch.object(
        index.eauto,
        "fetch_upcoming_events",
        return_value=[mock_event],
    )
    mock_event.name = "Test Event"
    result = json.loads(client.get("/events/upcoming").data.decode("utf8"))
    assert isinstance(result["events"], list)
    for k in (
        "id",
        "name",
        "description",
        "instructor",
        "start",
        "end",
        "capacity",
        "url",
        "registration",
    ):
        assert k in result["events"][0]


def test_upcoming_events(mocker, client):
    """Test upcoming_events returns valid events sorted by date."""
    mocker.patch.object(index, "tznow", return_value=d(0))
    mock_event = mocker.Mock(
        neon_id="123",
        description="Test Description",
        instructor_name="Instructor",
        start_date=d(1, 16),
        end_date=d(1, 19),
        capacity=10,
        url="http://example.com",
        registration=True,
        in_blocklist=False,
    )
    mock_event.name = "Test Event"

    mock_nostart_event = mocker.Mock(
        start_date=None,
    )

    mock_past_event = mocker.Mock(
        start_date=d(-2),
        end_date=d(-1),
        in_blocklist=False,
    )

    mock_blocked_event = mocker.Mock(
        start_date=d(1, 16),
        end_date=d(1, 19),
        in_blocklist=True,
    )

    mocker.patch.object(
        index.eauto,
        "fetch_upcoming_events",
        return_value=[
            mock_event,
            mock_nostart_event,
            mock_past_event,
            mock_blocked_event,
        ],
    )
    result = json.loads(client.get("/events/upcoming").data.decode("utf8"))

    assert len(result["events"]) == 1
    assert result["events"][0]["name"] == "Test Event"
    assert result["events"][0]["start"] == d(1, 16).isoformat()
    assert result["now"] == d(0).isoformat()


def test_event_ticket_info_eventbrite(mocker, client):
    """Test event_ticket_info handler with eventbrite ID"""

    # Test Eventbrite path
    mock_eb_event = mocker.MagicMock(
        ticket_options=[
            {
                "id": "eb123",
                "name": "Eventbrite Event",
                "price": 5.0,
                "total": 8,
                "sold": 3,
            }
        ]
    )
    mocker.patch.object(index.eventbrite, "is_valid_id", return_value=True)
    mocker.patch.object(index.eventbrite, "fetch_event", return_value=mock_eb_event)
    rep = client.get("/events/tickets?id=eb123")
    assert json.loads(rep.data.decode("utf8")) == mock_eb_event.ticket_options
    index.eventbrite.fetch_event.assert_called_once_with("eb123")


def test_event_ticket_info_neon(mocker, client):
    """Test event_ticket_info handler with neon ID"""
    mock_neon_event = mocker.MagicMock(
        ticket_options=[
            {
                "id": "eb123",
                "name": "Eventbrite Event",
                "price": 5.0,
                "total": 8,
                "sold": 3,
            }
        ]
    )
    mocker.patch.object(index.eventbrite, "is_valid_id", return_value=False)
    mocker.patch.object(index.neon, "fetch_event", return_value=mock_neon_event)
    rep = client.get("/events/tickets?id=neon456")
    assert json.loads(rep.data.decode("utf8")) == mock_neon_event.ticket_options
    neon.fetch_event.assert_called_once_with("neon456", fetch_tickets=True)


def test_event_ticket_info_no_id(mocker, client):
    rep = client.get("/events/tickets")
    assert rep.status != 200
