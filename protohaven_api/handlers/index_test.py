"""Verify proper behavior of public access pages"""

# pylint: skip-file
import json

import pytest

from protohaven_api.app import configure_app
from protohaven_api.config import get_config
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
        "event_discount_pct": 0,
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
        "event_discount_pct": 0,
        "roles": [],
    }


def test_class_listing(mocker, client):
    """Test class_listing function returns sorted class list with airtable data"""
    m1 = mocker.MagicMock(
        event_id="1", start_date=d(0, 10), description="foo", airtable_data="bar"
    )
    m1.name = "m1"
    m2 = mocker.MagicMock(
        event_id="2", start_date=d(0, 9), description="foo", airtable_data="baz"
    )
    m2.name = "m2"
    mocker.patch.object(index.eauto, "fetch_upcoming_events", return_value=[m1, m2])
    rep = client.get("/class_listing")
    assert json.loads(rep.data.decode("utf8")) == [
        {
            "id": "2",
            "name": "m2",
            "description": "foo",
            "timestamp": d(0, 9).isoformat(),
            "day": "Wednesday, Jan 1",
            "time": "9:00 AM",
            "airtable_data": "baz",
        },
        {
            "id": "1",
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
        event_id="123",
        description="Test Description",
        instructor_name="Instructor",
        display_category="Test",
        display_level="Level",
        start_date=d(1, 16),
        end_date=d(2, 19),
        sessions=[(d(1, 16), d(1, 19)), (d(2, 16), d(2, 19))],
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
        "humanized_session_info",
        "humanized_start",
        "category",
        "level",
        "capacity",
        "url",
        "registration",
    ):
        assert k in result["events"][0]


def test_upcoming_events(mocker, client):
    """Test upcoming_events returns valid events sorted by date."""
    mocker.patch.object(index, "tznow", return_value=d(0))
    mock_event = mocker.Mock(
        event_id="123",
        description="Test Description",
        instructor_name="Instructor",
        display_category="Test Category",
        display_level="Test Level",
        start_date=d(1, 16),
        end_date=d(2, 19),
        capacity=10,
        sessions=[(d(1, 16), d(1, 19)), (d(2, 16), d(2, 19))],
        url="http://example.com",
        image_url="http://test.net",
        registration=True,
        in_blocklist=lambda: False,
    )
    mock_event.name = "Test Event"

    mock_nostart_event = mocker.Mock(
        start_date=None,
        sessions=None,
    )

    mock_past_event = mocker.Mock(
        start_date=d(-2),
        end_date=d(-1),
        sessions=None,
        in_blocklist=lambda: False,
    )

    mock_blocked_event = mocker.Mock(
        start_date=d(1, 16),
        end_date=d(1, 19),
        sessions=None,
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
    assert result["events"][0]["humanized_start"] == "Thu, Jan 02, 04:00PM"
    assert result["events"][0]["humanized_session_info"] == "2 Sessions, 3h Each"
    assert result["events"][0]["category"] == "Test Category"
    assert result["events"][0]["level"] == "Test Level"
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
            "startDate": d(0, 10),  # 10 AM (open)
            "endDate": d(0, 13),  # 1pm
            "firstName": "Jane",
            "lastName": "Smith",
            "resourceName": "3D Printing - 3D Printer",
            "referenceNumber": "REF002",
        },
        {
            "startDate": d(0, 15),  # 3 PM
            "endDate": d(0, 22),  # 10 PM (close)
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
    mocker.patch.object(index.booked, "cache", mock_cache)

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
        elif i == 1:  # 3D Printer at 10 AM (open)
            assert reservation["start"] == "open"
            assert reservation["end"] == "1:00 PM"
        elif i == 2:  # CNC Router at 3 PM, close
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


def test_humanize_sessions(mocker):
    """Test formatting of session info"""
    assert index.humanize_sessions(mocker.MagicMock(airtable_data=None)) == None
    assert index.humanize_sessions(mocker.MagicMock(sessions=[])) == None
    assert (
        index.humanize_sessions(mocker.MagicMock(sessions=[(d(1, 16), d(1, 19))]))
        == "Single 3h Class"
    )
    assert (
        index.humanize_sessions(mocker.MagicMock(sessions=[(d(1, 16), d(1, 19.52))]))
        == "Single 3.5h Class"
    )
    assert (
        index.humanize_sessions(
            mocker.MagicMock(sessions=[(d(1, 16), d(1, 19)), (d(2, 16), d(2, 19))])
        )
        == "2 Sessions, 3h Each"
    )
    assert (
        index.humanize_sessions(
            mocker.MagicMock(sessions=[(d(1, 16), d(1, 19)), (d(2, 16), d(2, 21))])
        )
        == "2 Sessions, Various Times"
    )
    assert (
        index.humanize_sessions(
            mocker.MagicMock(
                sessions=[(d(1, 16), d(1, 19.52)), (d(2, 16), d(2, 19.52))]
            )
        )
        == "2 Sessions, 3.5h Each"
    )


def test_user_enroll_nfc_no_data(client):
    """Test enroll_nfc returns 400 when no JSON body"""
    rep = client.post(
        "/member/enroll_nfc", data="not json", content_type="application/json"
    )
    assert rep.status_code == 400


def test_user_enroll_nfc_missing_fields(mocker, client):
    """Test enroll_nfc returns 400 when missing required fields"""
    rep = client.post("/member/enroll_nfc", json={"neon_id": "123"})
    assert rep.status_code == 400
    rep = client.post("/member/enroll_nfc", json={"email": "a@b.com"})
    assert rep.status_code == 400


def test_user_enroll_nfc_success(mocker, client):
    """Test enroll_nfc publishes MQTT message and returns ok"""
    mock_mqtt = mocker.MagicMock()
    nfc_enroll_topic = get_config("mqtt/nfc_enroll_topic")
    mocker.patch.object(index.mqtt, "get", return_value=mock_mqtt)

    rep = client.post("/member/enroll_nfc", json={"neon_id": "123", "email": "a@b.com"})
    assert rep.status_code == 200
    assert rep.json["status"] == "ok"
    mock_mqtt.c.publish.assert_called_once()
    call_args = mock_mqtt.c.publish.call_args[0]
    assert call_args[0] == nfc_enroll_topic


def test_user_enroll_nfc_no_mqtt(mocker, client):
    """Test enroll_nfc returns 503 when no MQTT client"""
    mocker.patch.object(index.mqtt, "get", return_value=None)

    rep = client.post("/member/enroll_nfc", json={"neon_id": "123", "email": "a@b.com"})
    assert rep.status_code == 503


def test_store_nfc_write_info_invalid_data(mocker):
    """Test _store_nfc_write_info logs error on missing fields"""
    mock_log = mocker.patch.object(index, "log")

    index._store_nfc_write_info({})
    mock_log.error.assert_called()

    index._store_nfc_write_info({"neon_id": "123", "timestamp": "2024-01-01"})
    mock_log.error.assert_called()


def test_store_nfc_write_info_success(mocker):
    """Test _store_nfc_write_info appends token and updates Neon"""
    mock_member = mocker.MagicMock()
    mock_member.nfc_token_ids = [{"timestamp": "old_ts", "nfc_id": "old_id"}]
    mocker.patch.object(
        index.neon, "search_member_by_neon_id", return_value=mock_member
    )
    mock_set = mocker.patch.object(index, "set_custom_fields")

    index._store_nfc_write_info(
        {"neon_id": "123", "timestamp": "2024-06-01T12:00:00Z", "nfc_id": "abc123"},
    )

    mock_set.assert_called_once()
    call_args = mock_set.call_args[0]
    assert call_args[0] == "123"
    assert call_args[1][0] == index.CustomField.NFC_TOKEN_IDS
    import json

    tokens = json.loads(call_args[1][1])
    assert len(tokens) == 2
    assert tokens[1] == ["2024-06-01T12:00:00Z", "abc123"]


def test_store_nfc_write_info_no_existing_tokens(mocker):
    """Test _store_nfc_write_info with no existing tokens"""
    mock_member = mocker.MagicMock()
    mock_member.nfc_token_ids = []
    mocker.patch.object(
        index.neon, "search_member_by_neon_id", return_value=mock_member
    )
    mock_set = mocker.patch.object(index, "set_custom_fields")

    index._store_nfc_write_info(
        {"neon_id": "123", "timestamp": "2024-06-01T12:00:00Z", "nfc_id": "abc123"},
    )

    mock_set.assert_called_once()
    call_args = mock_set.call_args[0]
    import json

    tokens = json.loads(call_args[1][1])
    assert tokens == [["2024-06-01T12:00:00Z", "abc123"]]


def test_store_nfc_write_info_member_not_found(mocker):
    """Test _store_nfc_write_info when member lookup returns None"""
    mocker.patch.object(index.neon, "search_member_by_neon_id", return_value=None)
    mock_set = mocker.patch.object(index, "set_custom_fields")
    mock_log = mocker.patch.object(index, "log")

    index._store_nfc_write_info(
        {"neon_id": "999", "timestamp": "2024-06-01T12:00:00Z", "nfc_id": "abc123"},
    )

    mock_set.assert_called_once()
    call_args = mock_set.call_args[0]
    import json

    tokens = json.loads(call_args[1][1])
    assert tokens == [["2024-06-01T12:00:00Z", "abc123"]]


def test_welcome_neon_ws_no_mqtt(mocker):
    """welcome_neon_ws returns 500 when the MQTT client is unavailable"""
    ws = mocker.MagicMock()
    mocker.patch.object(index.mqtt, "get", return_value=None)
    rep = index.welcome_neon_ws(ws)
    assert rep.status_code == 500
    ws.send.assert_not_called()


def test_welcome_neon_ws_registers_handles_and_unregisters(mocker):
    """welcome_neon_ws subscribes to MQTT topics, forwards messages, and cleans up"""
    topics = {
        "mqtt/neon_signin_topic": "signin",
        "mqtt/neon_toast_topic": "toast",
        "mqtt/nfc_heartbeat_topic": "heartbeat",
        "mqtt/nfc_written_topic": "written",
    }
    mocker.patch.object(index, "get_config", side_effect=lambda k: topics[k])
    mocker.patch.object(index.time, "time", return_value=100)
    store = mocker.patch.object(index, "_store_nfc_write_info")

    mqtt_client = mocker.MagicMock()
    mqtt_client.c.is_connected.return_value = True
    mocker.patch.object(index.mqtt, "get", return_value=mqtt_client)

    ws = mocker.MagicMock()
    ws.receive.side_effect = [
        None,
        json.dumps({"type": "ping"}),
        json.dumps({"type": "other"}),
        RuntimeError("stop"),
    ]

    with pytest.raises(RuntimeError):
        index.welcome_neon_ws(ws)

    registered = {
        call.args[0]: call.args[1]
        for call in mqtt_client.register_topic_callback.call_args_list
    }
    assert set(registered) == set(topics.values())

    # Exercise each callback captured during registration.
    registered["signin"]("signin", {"neon_id": "123"})
    registered["heartbeat"]("heartbeat", {"ok": True})
    registered["written"](
        "written", {"neon_id": "123", "timestamp": "2025-01-01", "nfc_id": "abc"}
    )
    store.assert_called_once_with(
        {"neon_id": "123", "timestamp": "2025-01-01", "nfc_id": "abc"}
    )

    # The initial status, timeout status, ping/pong, and forwarded messages all
    # go through ws.send.
    sent = [json.loads(call.args[0]) for call in ws.send.call_args_list]
    assert sent[0]["type"] == "status"
    assert sent[0]["server_mqtt_connected"] is True
    assert sent[0]["nfc_heartbeat_age_sec"] is None
    assert any(msg.get("type") == "pong" for msg in sent)
    assert any(
        msg.get("origin") == "signin" and msg.get("data") == {"neon_id": "123"}
        for msg in sent
    )

    assert mqtt_client.unregister_topic_callback.call_count == 4
    assert (
        mqtt_client.unregister_topic_callback.call_args_list[2].kwargs["as_group"]
        is False
    )
    assert (
        mqtt_client.unregister_topic_callback.call_args_list[3].kwargs["as_group"]
        is False
    )
