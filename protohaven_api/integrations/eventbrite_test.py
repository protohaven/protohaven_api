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
        "POST", "/organizations/test_org_id/discounts/", expected_params
    )
