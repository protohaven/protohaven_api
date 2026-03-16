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


def test_whoami_no_roles(client):
    """test /whoami returns session info even if no role data"""
    setup_session(client, roles=None)
    response = client.get("/whoami")
    assert json.loads(response.data.decode("utf8")) == {
        "fullname": "First Last",
        "email": "foo@bar.com",
        "neon_id": 1234,
        "clearances": ["C1", "C2"],
        "roles": [],
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
    from protohaven_api.integrations import eventbrite as eb

    mocker.patch.object(eb, "is_valid_id", return_value=True)
    mocker.patch.object(eb, "fetch_event", return_value=mock_eb_event)
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
        image_url="http://imgurl.com",
        in_blocklist=lambda: False,
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
        image_url="http://test.net",
        registration=True,
        in_blocklist=lambda: False,
    )
    mock_event.name = "Test Event"

    mock_nostart_event = mocker.Mock(
        start_date=None,
    )

    mock_past_event = mocker.Mock(
        start_date=d(-2),
        end_date=d(-1),
        in_blocklist=lambda: False,
    )

    mock_blocked_event = mocker.Mock(
        start_date=d(1, 16),
        end_date=d(1, 19),
        in_blocklist=lambda: True,
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
    mocker.patch.object(index.eauto, "fetch_event", return_value=mock_eb_event)
    rep = client.get("/events/tickets?id=eb123")
    assert json.loads(rep.data.decode("utf8")) == mock_eb_event.ticket_options


def test_event_ticket_info_no_id(mocker, client):
    rep = client.get("/events/tickets")
    assert rep.status != 200


def test_neon_lookup(mocker, client):
    """Test neon_lookup returns structured data"""
    mock_member = mocker.MagicMock()
    mock_member.neon_id = "123"
    mock_member.fname = "John"
    mock_member.lname = "Doe"
    mock_member.email = "john@example.com"

    mocker.patch.object(index.neon.cache, "find_best_match", return_value=[mock_member])

    response = client.post("/neon_lookup", data={"search": "John"})
    assert response.status_code == 200
    result = json.loads(response.data.decode("utf8"))
    assert result == [
        {
            "neon_id": "123",
            "name": "John Doe",
            "email": "john@example.com",
            "display": "John Doe (#123)",
        }
    ]


def test_get_event_reservations(mocker, client):
    """Test reservations endpoint returns grouped data with areas"""
    # Mock the current time
    mock_now = d(0, 12)  # Noon
    mocker.patch.object(index, "tznow", return_value=mock_now)

    # Mock cache["reservations"] to return some test data
    mock_reservations = [
        {
            "startDate": d(0, 14),  # 2 PM
            "endDate": d(0, 16),  # 4 PM
            "firstName": "John",
            "lastName": "Doe",
            "resourceName": "Laser Lab - Laser Cutter",
            "referenceNumber": "REF001",
        },
        {
            "startDate": d(0, 10),  # 10 AM (before open)
            "endDate": d(0, 12),  # Noon
            "firstName": "Jane",
            "lastName": "Smith",
            "resourceName": "3D Printing - 3D Printer",
            "referenceNumber": "REF002",
        },
        {
            "startDate": d(0, 15),  # 3 PM
            "endDate": d(0, 22),  # 10 PM (after close)
            "firstName": "John",
            "lastName": "Doe",
            "resourceName": "Wood Shop - CNC Router",
            "referenceNumber": "REF003",
        },
    ]
    # Create a mock cache object
    mock_cache = mocker.MagicMock()
    mock_cache.__getitem__ = mocker.MagicMock(
        side_effect=lambda key: mock_reservations if key == "reservations" else None
    )
    mocker.patch.object(index, "cache", mock_cache)

    # Mock get_tools to return tool-area mappings
    mock_tools = [
        {
            "fields": {
                "Tool Name": "Laser Cutter",
                "Name (from Shop Area)": ["Laser Lab"],
            }
        },
        {
            "fields": {
                "Tool Name": "3D Printer",
                "Name (from Shop Area)": ["3D Printing"],
            }
        },
        {
            "fields": {
                "Tool Name": "CNC Router",
                "Name (from Shop Area)": ["Wood Shop"],
            }
        },
    ]
    mocker.patch.object(index.airtable, "get_tools", return_value=mock_tools)

    response = client.get("/events/reservations")
    assert response.status_code == 200

    result = json.loads(response.data.decode("utf8"))

    # Check that we have 3 reservations
    assert len(result) == 3

    # Check that each reservation has the expected structure
    expected_resources = ["Laser Cutter", "3D Printer", "CNC Router"]
    expected_areas = ["Laser Lab", "3D Printing", "Wood Shop"]
    expected_names = ["John Doe", "Jane Smith", "John Doe"]

    for i, reservation in enumerate(result):
        assert reservation["resource"] == expected_resources[i]
        assert reservation["area"] == expected_areas[i]
        assert reservation["name"] == expected_names[i]

        # Check time formatting
        if i == 0:  # Laser Cutter at 2 PM
            assert reservation["start"] == "2:00 PM"
            assert reservation["end"] == "4:00 PM"
        elif i == 1:  # 3D Printer at 10 AM (before open)
            assert reservation["start"] == "open"
            assert reservation["end"] == "12:00 PM"
        elif i == 2:  # CNC Router at 3 PM, ends after close
            assert reservation["start"] == "3:00 PM"
            assert reservation["end"] == "close"

        # Test with tool not found in airtable
        mock_reservations.append(
            {
                "startDate": d(0, 13),
                "endDate": d(0, 14),
                "firstName": "Bob",
                "lastName": "Jones",
                "resourceName": "Unknown Area - Unknown Tool",
                "referenceNumber": "REF004",
            }
        )

    response = client.get("/events/reservations")
    result = json.loads(response.data.decode("utf8"))

    # Find the unknown tool reservation
    unknown_res = next(r for r in result if r["resource"] == "Unknown Tool")
    assert unknown_res["area"] == "Unknown Area"
    assert unknown_res["name"] == "Bob Jones"
