"""Tests for eventbrite integration"""

# pylint: disable=protected-access,duplicate-code

import json
import tarfile
import tempfile
from pathlib import Path

import pytest
import requests

from protohaven_api.integrations import eventbrite as e
from protohaven_api.integrations.models import Attendee, Event
from protohaven_api.testing import d, t


def test_is_valid_id():
    """Test Eventbrite ID validation"""
    # Valid Eventbrite IDs
    assert e.is_valid_id("375402919237") is True
    assert e.is_valid_id("999999999999") is True

    # Invalid Eventbrite IDs (below threshold)
    assert e.is_valid_id("375402919236") is False
    assert e.is_valid_id("1") is False


def test_fetch_events(mocker):
    """Test fetching events from Eventbrite with pagination"""
    mock_conn = mocker.patch.object(e, "get_connector")
    mock_request = mock_conn.return_value.eventbrite_request

    # First page response
    mock_request.return_value = {
        "events": [{"id": "1", "name": "Event 1"}],
        "pagination": {"has_more_items": True, "continuation": "cont_token"},
    }

    # Second page response
    mock_request.side_effect = [
        mock_request.return_value,
        {
            "events": [{"id": "2", "name": "Event 2"}],
            "pagination": {"has_more_items": False},
        },
    ]

    events = list(e.fetch_events(include_ticketing=True, status="live"))

    assert len(events) == 2
    assert events[0].event_id == "1"
    assert events[1].event_id == "2"
    assert mock_request.call_count == 2


def test_events_backup(mocker):
    """Events backup archives Eventbrite event and attendee data"""
    mock_event = Event.from_eventbrite_search(
        {"id": "1", "ticket_classes": [{"id": "tc1"}]}
    )
    mock_event.set_attendee_data([{"id": "a1"}])
    mocker.patch.object(
        e,
        "fetch_events",
        return_value=iter([mock_event]),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "out.tar.gz"
        sz = e.events_backup(str(dest))
        assert sz > 0

        with tarfile.open(dest, "r:gz") as tar:
            got = tar.extractfile("events.json").read().decode("utf8")
            assert json.loads(got) == [
                {
                    "eventbrite_data": {"id": "1", "ticket_classes": [{"id": "tc1"}]},
                    "eventbrite_attendee_data": [{"id": "a1"}],
                }
            ]


def test_fetch_event(mocker):
    """Test fetching a single event from Eventbrite"""
    mock_response = {"id": "123", "name": {"text": "Test Event"}}
    mocker.patch.object(e.Event, "from_eventbrite_search", return_value=mock_response)
    mock_connector = mocker.Mock()
    mock_connector.eventbrite_request.return_value = mock_response
    mocker.patch.object(e, "get_connector", return_value=mock_connector)
    got = e.fetch_event("123")
    assert got == mock_response


def test_generate_discount_code(mocker):
    """Test creating an Eventbrite discount code"""
    mocker.patch.object(e, "tznow", return_value=d(0))
    mock_code = "ABC123XY"

    mocker.patch.object(e.uuid, "uuid4", return_value=mock_code)
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_connector = mocker.MagicMock()
    mock_connector.eventbrite_request.return_value = {"code": mock_code}
    mocker.patch.object(e, "get_connector", return_value=mock_connector)

    got = e.generate_discount_code(evt_id="456", percent_off=25, expiration_hours=4)

    assert got == mock_code
    expected_params = {
        "discount": {
            "type": "coded",
            "event_id": 456,
            "code": mock_code,
            "percent_off": "25",
            "quantity_available": 1,
            "end_date": "2025-01-01T09:00:00",
        }
    }
    mock_connector.eventbrite_request.assert_called_once_with(
        "POST", "/organizations/test_org_id/discounts/", json=expected_params
    )


def test_assign_pricing(mocker):
    """Test creating a ticket class with correct sales end time"""
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_connector = mocker.MagicMock()
    mock_connector.eventbrite_request.return_value = {
        "resource_uri": "/ticket_class/123/"
    }
    mocker.patch.object(e, "get_connector", return_value=mock_connector)

    got = e.assign_pricing("event_123", 50, 6)

    assert got == "/ticket_class/123/"
    expected_params = {
        "ticket_class": {
            "quantity_total": 6,
            "cost": "USD,5000",
            "free": False,
            "include_fee": True,
            "name": "General Admission",
            "sales_end_relative": {
                "relative_to_event": "start_time",
                "offset": 3600 * 24,  # 24 hours BEFORE event
            },
            "hide_sale_dates": True,
        }
    }
    mock_connector.eventbrite_request.assert_called_once_with(
        "POST", "/events/event_123/ticket_classes/", json=expected_params
    )


def test_assign_pricing_clear_existing(mocker):
    """Test creating a ticket class with clear_existing=True"""
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_connector = mocker.MagicMock()

    # Mock the event fetch response with existing ticket classes
    # and successful DELETE responses
    mock_connector.eventbrite_request.side_effect = [
        {"ticket_classes": [{"id": "ticket_456"}, {"id": "ticket_789"}]},
        None,  # DELETE response for ticket_456
        None,  # DELETE response for ticket_789
        {"resource_uri": "/ticket_class/123/"},
    ]

    mocker.patch.object(e, "get_connector", return_value=mock_connector)
    mocker.patch.object(e.log, "info")
    mocker.patch.object(e.log, "warning")

    got = e.assign_pricing("event_123", 50, 6, clear_existing=True)

    assert got == "/ticket_class/123/"

    # Should have called eventbrite_request 4 times:
    # 1. GET to fetch event with ticket classes
    # 2. DELETE for ticket_456
    # 3. DELETE for ticket_789
    # 4. POST to create new ticket class
    assert mock_connector.eventbrite_request.call_count == 4

    # Check the calls
    calls = mock_connector.eventbrite_request.call_args_list
    assert calls[0][0] == ("GET", "/events/event_123")
    assert calls[0][1]["params"] == {"expand": "ticket_classes"}

    # Check DELETE calls (order might vary)
    delete_urls = [call[0][1] for call in calls[1:3]]
    assert "/events/event_123/ticket_classes/ticket_456/" in delete_urls
    assert "/events/event_123/ticket_classes/ticket_789/" in delete_urls

    # Check the POST call to create new ticket class
    assert calls[3][0] == ("POST", "/events/event_123/ticket_classes/")


def test_fetch_events_preserves_attendee_data(mocker):
    """Attendee data fetched during event listing must be attached to yielded events"""
    raw_event = {"id": "1", "name": "Event 1"}
    mock_connector = mocker.MagicMock()
    mock_connector.eventbrite_request.return_value = {
        "events": [raw_event],
        "pagination": {"has_more_items": False},
    }
    mocker.patch.object(e, "get_connector", return_value=mock_connector)
    mocker.patch.object(e, "get_config", return_value="org")
    mocker.patch.object(
        e,
        "fetch_attendees",
        side_effect=lambda *args, **kwargs: iter([{"id": "attendee_1"}]),
    )

    batched = list(e.fetch_events(batching=True, attendees=True))
    assert len(batched) == 1
    assert len(batched[0]) == 1
    assert batched[0][0].eventbrite_attendee_data == [{"id": "attendee_1"}]

    mock_connector.eventbrite_request.return_value = {
        "events": [raw_event],
        "pagination": {"has_more_items": False},
    }
    unbatched = list(e.fetch_events(attendees=True))
    assert len(unbatched) == 1
    assert unbatched[0].eventbrite_attendee_data == [{"id": "attendee_1"}]


def test_register_attendee(mocker):
    """Registering an attendee creates an Eventbrite order"""
    mock_connector = mocker.MagicMock()
    mock_connector.eventbrite_request.return_value = {"id": "order_1"}
    mocker.patch.object(e, "get_connector", return_value=mock_connector)

    got = e.register_attendee(
        "event_1",
        "ticket_class_1",
        "First",
        "Last",
        "first@example.com",
        discount_code="FREE100",
    )

    assert got == {"id": "order_1"}
    mock_connector.eventbrite_request.assert_called_once_with(
        "POST",
        "/orders/",
        json={
            "order": {
                "email": "first@example.com",
                "first_name": "First",
                "last_name": "Last",
                "event_id": "event_1",
                "attendees": [
                    {
                        "ticket_class_id": "ticket_class_1",
                        "first_name": "First",
                        "last_name": "Last",
                        "email": "first@example.com",
                    }
                ],
                "discount_code": "FREE100",
            }
        },
    )


def test_cancel_attendee_order(mocker):
    """Cancelling by email cancels the matching free order"""
    mock_connector = mocker.MagicMock()
    mock_connector.eventbrite_request.return_value = {
        "id": "order_1",
        "cancelled": True,
    }
    mocker.patch.object(e, "get_connector", return_value=mock_connector)
    mocker.patch.object(
        e,
        "fetch_attendees",
        return_value=iter(
            [
                {
                    "id": "attendee_1",
                    "order_id": "order_1",
                    "cancelled": False,
                    "refunded": False,
                    "profile": {"email": "FIRST@example.com"},
                }
            ]
        ),
    )

    got = e.cancel_attendee_order("event_1", "first@example.com")

    assert got == {"id": "order_1", "cancelled": True}
    mock_connector.eventbrite_request.assert_called_once_with(
        "POST", "/orders/order_1/cancel/"
    )


def test_cancel_attendee_order_multiple_attendees_raises(mocker):
    """Do not cancel orders that contain multiple attendees"""
    mock_connector = mocker.MagicMock()
    mocker.patch.object(e, "get_connector", return_value=mock_connector)
    mocker.patch.object(
        e,
        "fetch_attendees",
        return_value=iter(
            [
                {
                    "id": "attendee_1",
                    "order_id": "order_1",
                    "profile": {"email": "first@example.com"},
                },
                {
                    "id": "attendee_2",
                    "order_id": "order_1",
                    "profile": {"email": "second@example.com"},
                },
            ]
        ),
    )

    try:
        e.cancel_attendee_order("event_1", "first@example.com")
    except RuntimeError as exc:
        assert "multiple attendees" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
    mock_connector.eventbrite_request.assert_not_called()


def test_eb_naive_local_utc_timestr_dst_edges():
    """Naive local UTC strings respect EST/EDT offsets"""
    assert e._eb_naive_local_utc_timestr(d(0)) == "2025-01-01T05:00:00"
    assert e._eb_naive_local_utc_timestr(d(181)) == "2025-07-01T04:00:00"


def test_utcfmt_dst_edges():
    """UTC formatter emits Z and respects EST/EDT offsets"""
    assert e._utcfmt(d(0)) == "2025-01-01T05:00:00Z"
    assert e._utcfmt(d(181)) == "2025-07-01T04:00:00Z"


@pytest.mark.parametrize(
    "include_ticketing,status,expected_params",
    [
        (True, None, {"expand": "ticket_classes"}),
        (False, None, {}),
        (False, "live", {"status": "live"}),
        (True, "live", {"status": "live", "expand": "ticket_classes"}),
    ],
)
def test_fetch_events_params(mocker, include_ticketing, status, expected_params):
    """fetch_events only sends requested query params"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {
        "events": [],
        "pagination": {"has_more_items": False},
    }
    mocker.patch.object(e, "get_connector", return_value=mock_conn)
    mocker.patch.object(e, "get_config", return_value="org")

    list(e.fetch_events(include_ticketing=include_ticketing, status=status))

    mock_conn.eventbrite_request.assert_called_once_with(
        "GET", "/organizations/org/events/", params=expected_params
    )


def test_fetch_events_batching_attendees_multipage(mocker):
    """Attendee data is attached to each event on every paginated page"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.side_effect = [
        {
            "events": [{"id": "1"}],
            "pagination": {"has_more_items": True, "continuation": "cont_token"},
        },
        {
            "events": [{"id": "2"}],
            "pagination": {"has_more_items": False},
        },
    ]
    mocker.patch.object(e, "get_connector", return_value=mock_conn)
    mocker.patch.object(e, "get_config", return_value="org")
    mocker.patch.object(
        e,
        "fetch_attendees",
        side_effect=lambda event_id, raw: iter([{"id": f"attendee_{event_id}"}]),
    )

    batched = list(e.fetch_events(batching=True, attendees=True))

    assert len(batched) == 2
    assert batched[0][0].eventbrite_attendee_data == [{"id": "attendee_1"}]
    assert batched[1][0].eventbrite_attendee_data == [{"id": "attendee_2"}]
    assert mock_conn.eventbrite_request.call_args_list[1] == mocker.call(
        "GET",
        "/organizations/org/events/",
        params={
            "expand": "ticket_classes",
            "status": "live",
            "continuation": "cont_token",
        },
    )


def test_fetch_event_include_ticketing(mocker):
    """Fetching a single event can expand ticket classes"""
    mock_event = {"id": "123", "name": {"text": "Test Event"}}
    mocker.patch.object(e.Event, "from_eventbrite_search", return_value=mock_event)
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = mock_event
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.fetch_event("123", include_ticketing=True)

    assert got == mock_event
    mock_conn.eventbrite_request.assert_called_once_with(
        "GET", "/events/123", params={"expand": "ticket_classes"}
    )


def test_generate_discount_code_amount_off(mocker):
    """amount_off creates a fixed-value code and omits percent_off"""
    mocker.patch.object(e, "tznow", return_value=d(0))
    mock_code = "ABC123XY"
    mocker.patch.object(e.uuid, "uuid4", return_value=mock_code)
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"code": mock_code}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.generate_discount_code(evt_id="456", amount_off=75, expiration_hours=4)

    assert got == mock_code
    expected_params = {
        "discount": {
            "type": "coded",
            "event_id": 456,
            "code": mock_code,
            "amount_off": "75.00",
            "quantity_available": 1,
            "end_date": "2025-01-01T09:00:00",
        }
    }
    mock_conn.eventbrite_request.assert_called_once_with(
        "POST", "/organizations/test_org_id/discounts/", json=expected_params
    )


def test_generate_discount_code_org_wide(mocker):
    """Leaving evt_id None creates an org-wide discount"""
    mocker.patch.object(e, "tznow", return_value=d(0))
    mock_code = "ABC123XY"
    mocker.patch.object(e.uuid, "uuid4", return_value=mock_code)
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"code": mock_code}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.generate_discount_code(evt_id=None, percent_off=25, expiration_hours=4)

    assert got == mock_code
    params = mock_conn.eventbrite_request.call_args[1]["json"]["discount"]
    assert "event_id" not in params
    assert params["percent_off"] == "25"


def test_generate_discount_code_requires_exactly_one_discount_type():
    """Neither or both percent_off/amount_off is rejected"""
    for kwargs in (
        {"evt_id": None, "percent_off": None, "amount_off": None},
        {"evt_id": None, "percent_off": 25, "amount_off": 10},
    ):
        with pytest.raises(RuntimeError):
            e.generate_discount_code(**kwargs)


def test_generate_discount_code_missing_code_raises(mocker):
    """A successful request with no code is treated as a failure"""
    mocker.patch.object(e, "tznow", return_value=d(0))
    mocker.patch.object(e.uuid, "uuid4", return_value="ABC123XY")
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    with pytest.raises(RuntimeError):
        e.generate_discount_code(evt_id="456", percent_off=25)


def test_create_event_single_session(mocker):
    """Single-session events get a full Eventbrite create payload"""
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"id": "event_123"}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    start = d(0, h=9)
    end = d(0, h=11)
    got = e.create_event(
        "Class",
        [(start, end)],
        summary="A summary",
        max_attendees=5,
        published=False,
        logo_id=7,
    )

    assert got == "event_123"
    body = mock_conn.eventbrite_request.call_args[1]["json"]["event"]
    assert body["name"] == {"html": "Class"}
    assert body["start"] == {"timezone": "America/New_York", "utc": e._utcfmt(start)}
    assert body["end"] == {"timezone": "America/New_York", "utc": e._utcfmt(end)}
    assert body["venue_id"] == "103409419"
    assert body["currency"] == "USD"
    assert body["listed"] is False
    assert body["show_remaining"] is True
    assert body["capacity"] == 5
    assert body["summary"] == "A summary"
    assert body["logo_id"] == 7


def test_create_event_multi_session_appends_session_count(mocker):
    """Multiple sessions are reflected in the generated event name"""
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"id": "event_123"}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    e.create_event(
        "Class",
        [(t(9), t(11)), (t(13), t(15))],
    )

    body = mock_conn.eventbrite_request.call_args[1]["json"]["event"]
    assert body["name"] == {"html": "Class (2 sessions)"}


def test_create_event_missing_id_raises(mocker):
    """Create responses must include the new event id"""
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"status": "ok"}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    with pytest.raises(RuntimeError):
        e.create_event("Class", [(t(9), t(11))])


def test_set_structured_content(mocker):
    """Structured content posts the overview body to the versioned endpoint"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"page_version_number": 2}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.set_structured_content("event_1", "Some description")

    assert got == 2
    mock_conn.eventbrite_request.assert_called_once_with(
        "POST",
        "/events/event_1/structured_content/2/",
        json={
            "access_type": "public",
            "modules": [
                {
                    "data": {
                        "body": {
                            "alignment": "left",
                            "text": "Some description",
                        }
                    },
                    "layout": "image_left",
                    "type": "text",
                }
            ],
            "purpose": "listing",
        },
    )


def test_set_structured_content_missing_version_raises(mocker):
    """A response without page_version_number is a failure"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    with pytest.raises(RuntimeError):
        e.set_structured_content("event_1", "Some description")


def test_assign_pricing_free_ticket(mocker):
    """Free ticket classes omit cost and set free=True"""
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"resource_uri": "/ticket_class/123/"}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.assign_pricing("event_123", 0, 4)

    assert got == "/ticket_class/123/"
    ticket_class = mock_conn.eventbrite_request.call_args[1]["json"]["ticket_class"]
    assert ticket_class["cost"] is None
    assert ticket_class["free"] is True
    assert ticket_class["quantity_total"] == 4


def test_assign_pricing_missing_resource_uri_raises(mocker):
    """A ticket-class response without resource_uri is a failure"""
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    with pytest.raises(RuntimeError):
        e.assign_pricing("event_123", 50, 6)


def test_assign_pricing_clear_existing_continues_when_delete_fails(mocker):
    """A failed ticket-class delete should not prevent creating a new one"""
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.side_effect = [
        {"ticket_classes": [{"id": "ticket_456"}]},
        RuntimeError("Eventbrite DELETE failed"),
        {"resource_uri": "/ticket_class/123/"},
    ]
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.assign_pricing("event_123", 50, 6, clear_existing=True)

    assert got == "/ticket_class/123/"
    assert mock_conn.eventbrite_request.call_args_list[2][0] == (
        "POST",
        "/events/event_123/ticket_classes/",
    )


def test_delete_event_unsafe(mocker):
    """Delete event sends DELETE to the event endpoint"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"deleted": True}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.delete_event_unsafe("event_1")

    assert got == {"deleted": True}
    mock_conn.eventbrite_request.assert_called_once_with("DELETE", "/events/event_1")


def test_set_event_scheduled_state_publish(mocker):
    """Publish posts to the publish endpoint and returns the response"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"published": True}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.set_event_scheduled_state("event_1")

    assert got == {"published": True}
    mock_conn.eventbrite_request.assert_called_once_with(
        "POST", "/events/event_1/publish/"
    )


def test_set_event_scheduled_state_publish_missing_published_raises(mocker):
    """Publish responses must include published=True"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    with pytest.raises(RuntimeError):
        e.set_event_scheduled_state("event_1")


def test_set_event_scheduled_state_unpublish(mocker):
    """Unpublish posts to the unpublish endpoint and returns the response"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"unpublished": True}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.set_event_scheduled_state("event_1", scheduled=False)

    assert got == {"unpublished": True}
    mock_conn.eventbrite_request.assert_called_once_with(
        "POST", "/events/event_1/unpublish/"
    )


def test_set_event_scheduled_state_unpublish_missing_unpublished_raises(mocker):
    """Unpublish responses must include unpublished=True"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    with pytest.raises(RuntimeError):
        e.set_event_scheduled_state("event_1", scheduled=False)


def test_upload_logo_image(mocker):
    """Logo upload follows the S3 token flow and returns the media id"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.side_effect = [
        {
            "upload_url": "https://s3.example/upload",
            "upload_data": {"key": "value"},
            "file_parameter_name": "file",
            "upload_token": "token_1",
        },
        {"id": "logo_1"},
    ]
    mocker.patch.object(e, "get_connector", return_value=mock_conn)
    mocker.patch.object(e, "get_config", return_value=30)

    mock_image = mocker.MagicMock()
    mock_image.headers = {"Content-Type": "image/png"}
    mock_image.content = b"image-bytes"
    mocker.patch.object(e.requests, "get", return_value=mock_image)
    mock_s3_response = mocker.MagicMock()
    mock_post = mocker.patch.object(e.requests, "post", return_value=mock_s3_response)

    got = e.upload_logo_image("https://example.com/logo.png")

    assert got == "logo_1"
    mock_image.raise_for_status.assert_called_once_with()
    mock_post.assert_called_once_with(
        "https://s3.example/upload",
        data={"key": "value"},
        files={
            "file": (
                "image.png",
                mocker.ANY,
                "image/png",
            )
        },
        timeout=30,
    )
    mock_s3_response.raise_for_status.assert_called_once_with()


def test_upload_logo_image_download_failure_raises(mocker):
    """An unreadable image URL fails before contacting Eventbrite"""
    mock_conn = mocker.MagicMock()
    mocker.patch.object(e, "get_connector", return_value=mock_conn)
    mocker.patch.object(
        e.requests,
        "get",
        side_effect=requests.exceptions.HTTPError("image download failed"),
    )

    with pytest.raises(requests.exceptions.HTTPError):
        e.upload_logo_image("https://example.com/logo.png")

    mock_conn.eventbrite_request.assert_not_called()


def test_upload_logo_image_missing_confirm_id_raises(mocker):
    """The confirm request must return a media id"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.side_effect = [
        {
            "upload_url": "https://s3.example/upload",
            "upload_data": {"key": "value"},
            "file_parameter_name": "file",
            "upload_token": "token_1",
        },
        {},
    ]
    mocker.patch.object(e, "get_connector", return_value=mock_conn)
    mocker.patch.object(e, "get_config", return_value=30)
    mock_image = mocker.MagicMock()
    mock_image.headers = {"Content-Type": "image/png"}
    mock_image.content = b"image-bytes"
    mocker.patch.object(e.requests, "get", return_value=mock_image)
    mock_s3_response = mocker.MagicMock()
    mocker.patch.object(e.requests, "post", return_value=mock_s3_response)

    with pytest.raises(RuntimeError):
        e.upload_logo_image("https://example.com/logo.png")


def test_fetch_attendees_pagination_and_raw(mocker):
    """Attendees are yielded across pages in raw or model form"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.side_effect = [
        {
            "attendees": [{"id": "a1"}],
            "pagination": {"has_more_items": True, "continuation": "cont_token"},
        },
        {
            "attendees": [{"id": "a2"}],
            "pagination": {"has_more_items": False},
        },
    ]
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    raw = list(e.fetch_attendees("event_1", raw=True))
    assert raw == [{"id": "a1"}, {"id": "a2"}]

    # The code mutates the same params dict after the first request, so assert
    # the stable second call explicitly and the URL of the first call.
    assert mock_conn.eventbrite_request.call_args_list[0][0] == (
        "GET",
        "/events/event_1/attendees/",
    )
    assert mock_conn.eventbrite_request.call_args_list[1] == mocker.call(
        "GET",
        "/events/event_1/attendees/",
        params={"continuation": "cont_token"},
    )

    mock_conn.eventbrite_request.reset_mock()
    mock_conn.eventbrite_request.side_effect = [
        {
            "attendees": [{"id": "a1"}],
            "pagination": {"has_more_items": False},
        }
    ]
    models = list(e.fetch_attendees("event_1"))
    assert isinstance(models[0], Attendee)
    assert models[0].eventbrite_data == {"id": "a1"}
    assert mock_conn.eventbrite_request.call_args_list[0] == mocker.call(
        "GET", "/events/event_1/attendees/", params={}
    )


@pytest.mark.parametrize(
    "first_name,last_name,email",
    [
        ("", "Last", "a@example.com"),
        ("First", "", "a@example.com"),
        ("First", "Last", ""),
    ],
)
def test_register_attendee_validation(mocker, first_name, last_name, email):
    """Missing required attendee fields are rejected before API call"""
    mock_conn = mocker.MagicMock()
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    with pytest.raises(RuntimeError):
        e.register_attendee("event_1", "ticket_class_1", first_name, last_name, email)

    mock_conn.eventbrite_request.assert_not_called()


def test_register_attendee_no_discount(mocker):
    """Registering without a discount code omits discount_code"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"id": "order_1"}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.register_attendee(
        "event_1", "ticket_class_1", "First", "Last", "first@example.com"
    )

    assert got == {"id": "order_1"}
    order = mock_conn.eventbrite_request.call_args[1]["json"]["order"]
    assert "discount_code" not in order


def test_register_attendee_missing_order_id_raises(mocker):
    """An order response without id is a failure"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    with pytest.raises(RuntimeError):
        e.register_attendee(
            "event_1", "ticket_class_1", "First", "Last", "first@example.com"
        )


def test_cancel_attendee_order_empty_email(mocker):
    """Empty target email returns None without looking up attendees"""
    mock_conn = mocker.MagicMock()
    mocker.patch.object(e, "get_connector", return_value=mock_conn)
    mock_fetch = mocker.patch.object(e, "fetch_attendees")

    assert e.cancel_attendee_order("event_1", "") is None
    assert e.cancel_attendee_order("event_1", "  ") is None
    mock_fetch.assert_not_called()
    mock_conn.eventbrite_request.assert_not_called()


def test_cancel_attendee_order_no_match(mocker):
    """No matching attendee returns None without cancelling an order"""
    mock_conn = mocker.MagicMock()
    mocker.patch.object(e, "get_connector", return_value=mock_conn)
    mocker.patch.object(
        e,
        "fetch_attendees",
        return_value=iter(
            [{"id": "a1", "order_id": "o1", "profile": {"email": "other@example.com"}}]
        ),
    )

    assert e.cancel_attendee_order("event_1", "first@example.com") is None
    mock_conn.eventbrite_request.assert_not_called()


def test_cancel_attendee_order_skips_cancelled_and_refunded(mocker):
    """Cancelled/refunded attendees are not eligible for cancellation"""
    mock_conn = mocker.MagicMock()
    mocker.patch.object(e, "get_connector", return_value=mock_conn)
    mocker.patch.object(
        e,
        "fetch_attendees",
        return_value=iter(
            [
                {
                    "id": "a1",
                    "order_id": "o1",
                    "cancelled": True,
                    "profile": {"email": "first@example.com"},
                },
                {
                    "id": "a2",
                    "order_id": "o2",
                    "refunded": True,
                    "profile": {"email": "first@example.com"},
                },
            ]
        ),
    )

    assert e.cancel_attendee_order("event_1", "first@example.com") is None
    mock_conn.eventbrite_request.assert_not_called()


def test_cancel_attendee_order_missing_order_id(mocker):
    """A matching attendee without an order id cannot be cancelled"""
    mock_conn = mocker.MagicMock()
    mocker.patch.object(e, "get_connector", return_value=mock_conn)
    mocker.patch.object(
        e,
        "fetch_attendees",
        return_value=iter([{"id": "a1", "profile": {"email": "first@example.com"}}]),
    )

    assert e.cancel_attendee_order("event_1", "first@example.com") is None
    mock_conn.eventbrite_request.assert_not_called()


def test_cancel_order(mocker):
    """Cancel order sends POST to the order cancel endpoint"""
    mock_conn = mocker.MagicMock()
    mock_conn.eventbrite_request.return_value = {"id": "order_1", "cancelled": True}
    mocker.patch.object(e, "get_connector", return_value=mock_conn)

    got = e.cancel_order("order_1")

    assert got == {"id": "order_1", "cancelled": True}
    mock_conn.eventbrite_request.assert_called_once_with(
        "POST", "/orders/order_1/cancel/"
    )
