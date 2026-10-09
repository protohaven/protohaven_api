"""Tests for event automation module"""

from protohaven_api.automation.classes import events as eauto
from protohaven_api.testing import d


def test_fetch_upcoming_events_eventbrite_only(mocker):
    """Upcoming events come from Eventbrite and are merged with Airtable"""
    mocker.patch.object(eauto, "tznow", return_value=d(0))
    mock_event = mocker.Mock(end_date=d(1), event_id="event_1", published=True)
    mock_fetch = mocker.patch.object(
        eauto.eventbrite,
        "fetch_events",
        return_value=[[mock_event]],
    )
    airtable_row = {"fields": {"Event ID": "event_1", "Name": "Test"}}
    mocker.patch.object(
        eauto.airtable,
        "get_class_automation_schedule_raw",
        return_value=[airtable_row],
    )

    got = list(eauto.fetch_upcoming_events(merge_airtable=True))

    assert got == [mock_event]
    mock_fetch.assert_called_once_with(
        status="live,started,ended,completed",
        batching=True,
        attendees=False,
    )
    mock_event.set_airtable_data.assert_called_once_with(airtable_row)


def test_fetch_upcoming_events_published_filter(mocker):
    """published=True filters out unlisted Eventbrite events"""
    mocker.patch.object(eauto, "tznow", return_value=d(0))
    listed = mocker.Mock(end_date=d(1), event_id="listed", published=True)
    unlisted = mocker.Mock(end_date=d(2), event_id="unlisted", published=False)
    mocker.patch.object(
        eauto.eventbrite,
        "fetch_events",
        return_value=[[listed, unlisted]],
    )

    assert list(eauto.fetch_upcoming_events(published=True)) == [listed]
    assert list(eauto.fetch_upcoming_events(published=False)) == [listed, unlisted]


def test_fetch_upcoming_events_filters_stale_events(mocker):
    """Events whose end date is before the trailing window are skipped"""
    mocker.patch.object(eauto, "tznow", return_value=d(0))
    stale = mocker.Mock(end_date=d(-8), event_id="stale", published=True)
    current = mocker.Mock(end_date=d(1), event_id="current", published=True)
    mocker.patch.object(
        eauto.eventbrite,
        "fetch_events",
        return_value=[[stale, current]],
    )

    assert list(eauto.fetch_upcoming_events()) == [current]


def test_fetch_upcoming_events_attendees_callable(mocker):
    """A callable attendees selector is treated as truthy by Eventbrite"""
    mocker.patch.object(eauto, "tznow", return_value=d(0))
    mock_event = mocker.Mock(end_date=d(1), event_id="event_1", published=True)
    mock_fetch = mocker.patch.object(
        eauto.eventbrite,
        "fetch_events",
        return_value=[[mock_event]],
    )

    list(eauto.fetch_upcoming_events(attendees=lambda evt: False))
    mock_fetch.assert_called_once_with(
        status="live,started,ended,completed", batching=True, attendees=True
    )


def test_airtable_merge_prefers_event_id_then_neon_id(mocker):
    """Airtable rows match Event ID first and fall back to Neon ID"""
    mocker.patch.object(eauto, "tznow", return_value=d(0))
    eb_event = mocker.Mock(end_date=d(1), event_id="eb_1", published=True)
    legacy_event = mocker.Mock(end_date=d(2), event_id="neon_1", published=True)
    mocker.patch.object(
        eauto.eventbrite,
        "fetch_events",
        return_value=[[eb_event, legacy_event]],
    )
    eb_row = {"fields": {"Event ID": "eb_1", "Neon ID": "wrong", "Name": "EB"}}
    legacy_row = {"fields": {"Neon ID": "neon_1", "Name": "Legacy"}}
    mocker.patch.object(
        eauto.airtable,
        "get_class_automation_schedule_raw",
        return_value=[eb_row, legacy_row],
    )

    got = list(eauto.fetch_upcoming_events(merge_airtable=True))
    assert got == [eb_event, legacy_event]
    eb_event.set_airtable_data.assert_called_once_with(eb_row)
    legacy_event.set_airtable_data.assert_called_once_with(legacy_row)


def test_fetch_event_eventbrite_only(mocker):
    """fetch_event delegates to Eventbrite with ticketing when requested"""
    mock_fetch = mocker.patch.object(eauto.eventbrite, "fetch_event", return_value=1)
    assert eauto.fetch_event("123", tickets=True, attendees=False) == 1
    mock_fetch.assert_called_once_with("123", include_ticketing=True)


def test_fetch_attendees_eventbrite_only(mocker):
    """fetch_attendees delegates to Eventbrite"""
    mock_fetch = mocker.patch.object(
        eauto.eventbrite, "fetch_attendees", return_value=["a1", "a2"]
    )
    assert list(eauto.fetch_attendees("123")) == ["a1", "a2"]
    mock_fetch.assert_called_once_with("123")


def test_set_event_scheduled_state_eventbrite_only(mocker):
    """set_event_scheduled_state delegates to Eventbrite"""
    mock_set = mocker.patch.object(
        eauto.eventbrite, "set_event_scheduled_state", return_value={"ok": True}
    )
    assert eauto.set_event_scheduled_state("123", scheduled=False) == {"ok": True}
    mock_set.assert_called_once_with("123", scheduled=False)
