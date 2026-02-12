"""Testing of tech shift commands"""

import datetime
from unittest.mock import Mock

import pytest

from protohaven_api.commands import blackouts as ts
from protohaven_api.testing import mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create cli test fixture for tech shift commands"""
    return mkcli(capsys, ts)


def test_sync_booked_blackouts_dry_run(mocker, cli):
    """Test dry run mode of sync_booked_blackouts"""
    # Mock forecast data
    mock_calendar_view = [
        {
            "date": "2024-01-01",
            "is_holiday": False,
            "AM": {"people": []},  # 0 techs
            "PM": {"people": [{"name": "Tech 1"}]}  # 1 tech
        },
        {
            "date": "2024-01-02",
            "is_holiday": True,  # Should be skipped
            "AM": {"people": []},
            "PM": {"people": []}
        },
    ]
    
    # Mock dependencies
    mocker.patch.object(ts.forecast, "generate", return_value={"calendar_view": mock_calendar_view})
    mocker.patch.object(ts.booked, "get_resources", return_value=[
        {"resourceId": "tool1", "name": "Test Tool 1"},
        {"resourceId": "tool2", "name": "Test Tool 2"}
    ])
    mocker.patch.object(ts.booked, "get_blackouts", return_value={"blackouts": []})
    mocker.patch("protohaven_api.commands.blackouts.tznow", return_value=datetime.datetime(2024, 1, 1, 0, 0, 0))
    
    # Run command in dry run mode
    result = cli("sync_booked_blackouts", ["--days-ahead", "2", "--no-apply"])
    
    # Verify results - result is a list with summary as first element
    assert len(result) == 1
    summary = result[0]
    assert summary["days_checked"] == 1  # Only non-holiday day
    assert summary["dry_run"] is True
    assert summary["blackouts_to_create"] == 1  # AM shift has 0 techs
    assert summary["blackouts_to_remove"] == 0  # No blackouts to remove
    assert len(summary["blackouts_created"]) == 0  # No blackouts created in dry run


def test_sync_booked_blackouts_with_apply(mocker, cli):
    """Test apply mode of sync_booked_blackouts"""
    # Mock forecast data
    mock_calendar_view = [
        {
            "date": "2024-01-01",
            "is_holiday": False,
            "AM": {"people": []},  # 0 techs
            "PM": {"people": []}   # 0 techs
        },
    ]
    
    # Mock dependencies
    mocker.patch.object(ts.forecast, "generate", return_value={"calendar_view": mock_calendar_view})
    mocker.patch.object(ts.booked, "get_resources", return_value=[
        {"resourceId": "tool1", "name": "Test Tool"}
    ])
    mocker.patch.object(ts.booked, "get_blackouts", return_value={"blackouts": []})
    mock_create = mocker.patch.object(ts.booked, "create_blackout", return_value={"blackoutId": "test123"})
    mocker.patch("protohaven_api.commands.blackouts.tznow", return_value=datetime.datetime(2024, 1, 1, 0, 0, 0))
    
    # Run command with apply
    result = cli("sync_booked_blackouts", ["--days-ahead", "1", "--apply"])
    
    # Verify results - result is a list with summary as first element
    assert len(result) == 1
    summary = result[0]
    assert summary["days_checked"] == 1
    assert summary["dry_run"] is False
    assert summary["blackouts_to_create"] == 1  # Full day (both shifts have 0 techs)
    assert summary["blackouts_to_remove"] == 0
    assert len(summary["blackouts_created"]) == 1
    
    # Verify create_blackout was called
    assert mock_create.called


def test_sync_booked_blackouts_existing_blackout(mocker, cli):
    """Test that existing blackouts are not recreated"""
    # Mock forecast data
    mock_calendar_view = [
        {
            "date": "2024-01-01",
            "is_holiday": False,
            "AM": {"people": []},  # 0 techs
            "PM": {"people": [{"name": "Tech 1"}]}
        },
    ]
    
    # Mock existing blackout for AM shift
    # Note: The command replaces "Z" with "+00:00" and parses with fromisoformat
    # Create timezone-aware datetimes for the mock
    am_start = datetime.datetime(2024, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    am_end = datetime.datetime(2024, 1, 1, 16, 0, 0, tzinfo=datetime.timezone.utc)
    
    mocker.patch.object(ts.forecast, "generate", return_value={"calendar_view": mock_calendar_view})
    mocker.patch.object(ts.booked, "get_resources", return_value=[{"resourceId": "tool1"}])
    mocker.patch.object(ts.booked, "get_blackouts", return_value={
        "blackouts": [{
            "id": "existing_blackout_123",
            "startDateTime": am_start.isoformat().replace("+00:00", "Z"),
            "endDateTime": am_end.isoformat().replace("+00:00", "Z")
        }]
    })
    mock_create = mocker.patch.object(ts.booked, "create_blackout")
    mock_delete = mocker.patch.object(ts.booked, "delete_blackout")
    mocker.patch("protohaven_api.commands.blackouts.tznow", return_value=datetime.datetime(2024, 1, 1, 0, 0, 0))
    
    # Run command
    result = cli("sync_booked_blackouts", ["--days-ahead", "1", "--no-apply"])
    
    # Verify no new blackouts needed (already exists) and existing one should NOT be removed (still needed)
    assert len(result) == 1
    summary = result[0]
    assert summary["blackouts_to_create"] == 0  # No new blackouts needed (already exists)
    assert summary["blackouts_to_remove"] == 0  # Existing blackout should NOT be removed (still needed - AM has 0 techs)
    assert not mock_create.called
    assert not mock_delete.called  # Not called in dry run

def test_sync_booked_blackouts_remove_blackouts(mocker, cli):
    """Test removal of blackouts when techs are now staffed"""
    # Mock forecast data - AM shift has techs, PM shift has techs
    mock_calendar_view = [
        {
            "date": "2024-01-01",
            "is_holiday": False,
            "AM": {"people": [{"name": "Tech 1"}]},  # 1 tech
            "PM": {"people": [{"name": "Tech 2"}]}   # 1 tech
        },
    ]
    
    # Mock existing blackouts that should be removed (techs are now staffed)
    am_start = datetime.datetime(2024, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    am_end = datetime.datetime(2024, 1, 1, 16, 0, 0, tzinfo=datetime.timezone.utc)
    pm_start = datetime.datetime(2024, 1, 1, 16, 0, 0, tzinfo=datetime.timezone.utc)
    pm_end = datetime.datetime(2024, 1, 1, 22, 0, 0, tzinfo=datetime.timezone.utc)
    
    mocker.patch.object(ts.forecast, "generate", return_value={"calendar_view": mock_calendar_view})
    mocker.patch.object(ts.booked, "get_resources", return_value=[{"resourceId": "tool1"}])
    mocker.patch.object(ts.booked, "get_blackouts", return_value={
        "blackouts": [
            {
                "id": "am_blackout_123",
                "startDateTime": am_start.isoformat().replace("+00:00", "Z"),
                "endDateTime": am_end.isoformat().replace("+00:00", "Z")
            },
            {
                "id": "pm_blackout_456",
                "startDateTime": pm_start.isoformat().replace("+00:00", "Z"),
                "endDateTime": pm_end.isoformat().replace("+00:00", "Z")
            }
        ]
    })
    mock_create = mocker.patch.object(ts.booked, "create_blackout")
    mock_delete = mocker.patch.object(ts.booked, "delete_blackout")
    mocker.patch("protohaven_api.commands.blackouts.tznow", return_value=datetime.datetime(2024, 1, 1, 0, 0, 0))
    
    # Run command with apply
    result = cli("sync_booked_blackouts", ["--days-ahead", "1", "--apply"])
    
    # Verify blackouts should be removed (techs are now staffed)
    assert len(result) == 1
    summary = result[0]
    assert summary["blackouts_to_create"] == 0  # No new blackouts needed
    assert summary["blackouts_to_remove"] == 2  # Both AM and PM blackouts should be removed
    assert len(summary["blackouts_removed"]) == 2  # Blackouts were actually removed
    
    # Verify delete_blackout was called twice
    assert mock_delete.call_count == 2
    assert not mock_create.called
