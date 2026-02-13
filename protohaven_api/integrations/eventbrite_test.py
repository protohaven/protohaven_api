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
    assert events[0].neon_id == "1"
    assert events[1].neon_id == "2"
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

    mocker.patch.object(e.random, "choices", return_value=list(mock_code))
    mocker.patch.object(e, "get_config", return_value="test_org_id")
    mock_connector = mocker.MagicMock()
    mock_connector.eventbrite_request.return_value = {"id": mock_code}
    mocker.patch.object(e, "get_connector", return_value=mock_connector)

    got = e.generate_discount_code("456", 25, 4)

    assert got == mock_code
    expected_params = {
        "discount": {
            "type": "coded",
            "event_id": "456",
            "code": mock_code,
            "percent_off": "25",
            "currency": "USD",
            "quantity_available": 1,
            "end_date": "2025-01-01T04:00:00Z",
            "start_date": "2025-01-01T00:00:00Z",
            "ticket_classes": [],
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
            "name": "General Admission",
            "sales_end_relative": {
                "relative_to_event": "start_time",
                "offset": -3600 * 24,  # 24 hours BEFORE event
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
