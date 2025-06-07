"""Tests for event automation module"""

from protohaven_api.automation.classes import events as eauto
from protohaven_api.testing import d


def test_fetch_upcoming_events_neon(mocker):
    """Test _fetch_upcoming_events_neon with various configurations"""
    mock_event = mocker.Mock(neon_id=1)
    mocker.patch.object(eauto.Event, "from_neon_fetch", return_value=mock_event)
    m1 = mocker.patch.object(
        eauto.neon_base, "paginated_fetch", return_value=[{"id": 1}]
    )
    mocker.patch.object(eauto.neon, "fetch_attendees", return_value=["a1", "a2"])
    mocker.patch.object(
        eauto.neon, "fetch_tickets_internal_do_not_use_directly", return_value=["t1"]
    )

    # Test basic fetch
    after = d(0)
    events = list(eauto.fetch_upcoming_events_neon(after))
    assert len(events) == 1
    m1.assert_called_with(
        "api_key1",
        "/events",
        {"endDateAfter": "2025-01-01", "archived": False, "publishedEvent": True},
    )

    # Test with airtable data
    airtable_row = {"fields": {"Name": "Test Event"}}
    events = list(
        eauto.fetch_upcoming_events_neon(after, airtable_map={1: airtable_row})
    )
    mock_event.set_airtable_data.assert_called_with(airtable_row)

    # Test with attendees and tickets
    list(
        eauto.fetch_upcoming_events_neon(
            after, fetch_attendees=True, fetch_tickets=True
        )
    )
    mock_event.set_attendee_data.assert_called_with(["a1", "a2"])
    mock_event.set_ticket_data.assert_called_with(["t1"])


def test_fetch_upcoming_events(mocker):
    """Test fetch_upcoming_events integration"""
    mocker.patch.object(eauto, "tznow", return_value=d(0))
    mock_neon_event = mocker.Mock(end_date=d(1))
    mock_eb_event = mocker.Mock(end_date=d(2))
    m1 = mocker.patch.object(
        eauto, "fetch_upcoming_events_neon", return_value=[mock_neon_event]
    )
    mocker.patch.object(eauto.eventbrite, "fetch_events", return_value=[mock_eb_event])
    mocker.patch.object(
        eauto.airtable,
        "get_class_automation_schedule",
        return_value=[{"fields": {"Neon ID": 1, "Name": "Test"}}],
    )

    # Test without airtable merge
    events = list(eauto.fetch_upcoming_events(back_days=7))
    assert len(events) == 2
    m1.assert_called_with(mocker.ANY, True, None, False, False)

    # Test with airtable merge
    events = list(eauto.fetch_upcoming_events(merge_airtable=True))
    mock_eb_event.set_airtable_data.assert_called_once()
