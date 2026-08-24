"""Tests for eventbrite integration"""

from protohaven_api.integrations import eventbrite as e
from protohaven_api.testing import d


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
