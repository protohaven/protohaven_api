"""Unit tests for eventbrite dev mock"""

import json

from protohaven_api.integrations.data import dev_eventbrite as e


def test_get_events(mocker):
    """Test get_events returns mock event data from airtable"""
    mock_records = [
        {"fields": {"data": {"id": "1", "name": "Test Event"}}},
        {"fields": {"data": {"id": "2", "name": "Another Event"}}},
    ]
    mocker.patch.object(e.airtable_base, "get_all_records", return_value=mock_records)

    resp = json.loads(e.handle("GET", "/organizations/123/events/").data.decode("utf8"))
    assert resp == {
        "events": [
            {"id": "1", "name": "Test Event"},
            {"id": "2", "name": "Another Event"},
        ],
        "pagination": {"has_more_items": False},
    }


def test_get_event(mocker):
    """Test get_event endpoint returns correct event data or 404"""
    mock_records = [
        {"fields": {"event_id": "123", "data": {"name": "Test Event"}}},
        {"fields": {"event_id": "456", "data": {"name": "Another Event"}}},
    ]
    mocker.patch.object(e.airtable_base, "get_all_records", return_value=mock_records)

    # Test existing event
    resp = json.loads(e.handle("GET", "/events/123").data.decode("utf8"))
    assert resp == {"name": "Test Event"}

    # Test non-existent event
    resp = e.handle("GET", "/events/999")
    assert resp.status_code == 404
