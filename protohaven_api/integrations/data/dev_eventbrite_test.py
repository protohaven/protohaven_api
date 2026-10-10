"""Unit tests for eventbrite dev mock"""

import json

import pytest

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


def test_handle_unsupported_mode():
    """Only GET, POST, and DELETE are supported by the local mock"""
    with pytest.raises(RuntimeError):
        e.handle("PATCH", "/events/123")


def test_post_event(mocker):
    """POST /organizations/<org>/events/ stores an Eventbrite event"""
    mocker.patch.object(e.uuid, "uuid4", return_value="event_123")
    mock_insert = mocker.patch.object(e.airtable_base, "insert_records")

    resp = json.loads(
        e.handle(
            "POST",
            "/organizations/123/events/",
            json={"event": {"name": {"html": "Class"}}},
        ).data.decode("utf8")
    )

    assert resp == {"id": "event_123"}
    mock_insert.assert_called_once_with(
        [
            {
                "event_id": "event_123",
                "data": {"id": "event_123", "name": {"html": "Class"}},
            }
        ],
        "fake_eventbrite",
        "events",
    )


def test_post_discount():
    """Discount creation returns the generated code"""
    resp = json.loads(
        e.handle(
            "POST",
            "/organizations/123/discounts/",
            json={"discount": {"code": "ABC123XY"}},
        ).data.decode("utf8")
    )
    assert resp == {"code": "ABC123XY"}


def test_post_order():
    """Order creation returns an id plus the submitted order"""
    resp = json.loads(
        e.handle(
            "POST",
            "/orders/",
            json={
                "order": {
                    "email": "first@example.com",
                    "first_name": "First",
                    "last_name": "Last",
                    "event_id": "event_1",
                }
            },
        ).data.decode("utf8")
    )
    assert resp["id"] == "1"
    assert resp["email"] == "first@example.com"


def test_post_cancel_order():
    """Order cancellation returns a cancelled order id"""
    resp = json.loads(e.handle("POST", "/orders/order_1/cancel/").data.decode("utf8"))
    assert resp == {"id": "order_1", "cancelled": True}


def test_post_ticket_class(mocker):
    """Ticket class creation returns a resource_uri"""
    mocker.patch.object(e.uuid, "uuid4", return_value="ticket_123")
    resp = json.loads(
        e.handle(
            "POST",
            "/events/event_1/ticket_classes/",
            json={"ticket_class": {"name": "General Admission"}},
        ).data.decode("utf8")
    )
    assert resp == {"resource_uri": "/ticket_class/ticket_123/"}


def test_delete_event():
    """Event deletion returns a success payload"""
    resp = json.loads(e.handle("DELETE", "/events/event_1").data.decode("utf8"))
    assert resp == {"deleted": True}


def test_delete_ticket_class():
    """Ticket class deletion returns a success payload"""
    resp = json.loads(
        e.handle("DELETE", "/events/event_1/ticket_classes/ticket_1/").data.decode(
            "utf8"
        )
    )
    assert resp == {"deleted": True}


def test_publish_event():
    """Publish endpoint returns published=True"""
    resp = json.loads(e.handle("POST", "/events/event_1/publish/").data.decode("utf8"))
    assert resp == {"published": True}


def test_unpublish_event():
    """Unpublish endpoint returns unpublished=True"""
    resp = json.loads(
        e.handle("POST", "/events/event_1/unpublish/").data.decode("utf8")
    )
    assert resp == {"unpublished": True}


def test_post_structured_content():
    """Structured content returns the requested page version"""
    resp = json.loads(
        e.handle(
            "POST",
            "/events/event_1/structured_content/3/",
            json={"modules": []},
        ).data.decode("utf8")
    )
    assert resp == {"page_version_number": 3}


def test_get_attendees():
    """Attendee endpoint returns an empty page by default"""
    resp = json.loads(e.handle("GET", "/events/event_1/attendees/").data.decode("utf8"))
    assert resp == {"attendees": [], "pagination": {"has_more_items": False}}


def test_media_upload_get(mocker):
    """Media upload GET returns S3 upload details"""
    mocker.patch.object(e.uuid, "uuid4", return_value="token_1")
    resp = json.loads(e.handle("GET", "/media/upload/").data.decode("utf8"))
    assert resp == {
        "upload_url": "https://s3.example/upload",
        "upload_data": {"key": "value"},
        "file_parameter_name": "file",
        "upload_token": "token_1",
    }


def test_media_upload_post():
    """Media upload POST returns the confirmed media id"""
    resp = json.loads(
        e.handle(
            "POST", "/media/upload/", json={"upload_token": "token_1"}
        ).data.decode("utf8")
    )
    assert resp == {"id": "token_1"}
