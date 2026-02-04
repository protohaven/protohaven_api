"""Tests for event automation module"""

# pylint: skip-file

import pytest

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
    events = list(eauto._fetch_upcoming_events_neon(after))
    assert len(events) == 1
    m1.assert_called_with(
        "api_key1",
        "/events",
        {"endDateAfter": "2025-01-01", "archived": False, "publishedEvent": True},
        batching=True,
    )

    # Test with attendees and tickets
    list(
        eauto._fetch_upcoming_events_neon(
            after, attendees=True, tickets=True
        )
    )
    mock_event.set_attendee_data.assert_called_with(["a1", "a2"])
    mock_event.set_ticket_data.assert_called_with(["t1"])


def test_fetch_upcoming_events(mocker):
    """Test fetch_upcoming_events integration"""
    mocker.patch.object(eauto, "tznow", return_value=d(0))
    mock_neon_event = mocker.Mock(end_date=d(1), neon_id=1)
    mock_eb_event = mocker.Mock(end_date=d(2), neon_id=1)
    m1 = mocker.patch.object(
        eauto,
        "_fetch_upcoming_events_neon",
        return_value=(lambda: (yield [mock_neon_event]))(),
    )
    mocker.patch.object(
        eauto.eventbrite,
        "fetch_events",
        return_value=(lambda: (yield [mock_eb_event]))(),
    )
    ad = {"fields": {"Neon ID": 1, "Name": "Test"}}
    mocker.patch.object(
        eauto.airtable,
        "get_class_automation_schedule",
        return_value=[ad],
    )

    events = list(eauto.fetch_upcoming_events(merge_airtable=True))
    mock_neon_event.set_airtable_data.assert_called_with(ad)
    mock_eb_event.set_airtable_data.assert_called_with(ad)


def test_fetch_upcoming_events_neon_conditional_attendees(mocker):
    """Test _fetch_upcoming_events_neon with a callable for `fetch_attendees`"""
    mocker.patch.object(
        eauto.neon_base, "paginated_fetch", return_value=[[{"id": 1}, {"id": 2}]]
    )
    mocker.patch.object(
        eauto.neon,
        "fetch_attendees",
        return_value=[{"registratonStatus": "SUCCEEDED", "accountId": "a1"}],
    )

    got = list(
        eauto._fetch_upcoming_events_neon(
            d(0), attendees=lambda evt: evt.neon_id == 1
        )
    )
    assert got[0][0].neon_id == 1
    assert got[0][0].attendee_count == 1
    assert got[0][1].neon_id == 2
    with pytest.raises(RuntimeError):  # No attendee data
        print(got[0][1].attendee_count)
