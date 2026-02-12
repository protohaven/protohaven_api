"""Testing of tech shift commands"""

import datetime
from unittest.mock import Mock

import pytest

from protohaven_api.commands import tech_shifts as ts
from protohaven_api.testing import mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create cli test fixture for tech shift commands"""
    return mkcli(capsys, ts)


def test_block_tech_shift_reservations_dry_run(mocker, cli):
    """Test dry run mode of block_tech_shift_reservations"""
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
    mocker.patch("protohaven_api.commands.tech_shifts.tznow", return_value=datetime.datetime(2024, 1, 1, 0, 0, 0))
    
    # Run command in dry run mode
    result = cli("block_tech_shift_reservations", ["--days-ahead", "2", "--no-apply"])
    
    # Verify results - result is a list with summary as first element
    assert len(result) == 1
    summary = result[0]
    assert summary["days_checked"] == 1  # Only non-holiday day
    assert summary["dry_run"] is True
    assert summary["blackouts_needed"] == 1  # AM shift has 0 techs
    assert len(summary["blackouts_created"]) == 0  # No blackouts created in dry run


def test_block_tech_shift_reservations_with_apply(mocker, cli):
    """Test apply mode of block_tech_shift_reservations"""
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
    mocker.patch("protohaven_api.commands.tech_shifts.tznow", return_value=datetime.datetime(2024, 1, 1, 0, 0, 0))
    
    # Run command with apply
    result = cli("block_tech_shift_reservations", ["--days-ahead", "1", "--apply"])
    
    # Verify results - result is a list with summary as first element
    assert len(result) == 1
    summary = result[0]
    assert summary["days_checked"] == 1
    assert summary["dry_run"] is False
    assert summary["blackouts_needed"] == 1  # Full day (both shifts have 0 techs)
    assert len(summary["blackouts_created"]) == 1
    
    # Verify create_blackout was called
    assert mock_create.called


def test_block_tech_shift_reservations_existing_blackout(mocker, cli):
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
    am_start = datetime.datetime(2024, 1, 1, 9, 0, 0, tzinfo=datetime.timezone.utc)
    am_end = datetime.datetime(2024, 1, 1, 13, 0, 0, tzinfo=datetime.timezone.utc)
    
    mocker.patch.object(ts.forecast, "generate", return_value={"calendar_view": mock_calendar_view})
    mocker.patch.object(ts.booked, "get_resources", return_value=[{"resourceId": "tool1"}])
    mocker.patch.object(ts.booked, "get_blackouts", return_value={
        "blackouts": [{
            "startDateTime": am_start.isoformat().replace("+00:00", "Z"),
            "endDateTime": am_end.isoformat().replace("+00:00", "Z")
        }]
    })
    mock_create = mocker.patch.object(ts.booked, "create_blackout")
    mocker.patch("protohaven_api.commands.tech_shifts.tznow", return_value=datetime.datetime(2024, 1, 1, 0, 0, 0))
    
    # Run command
    result = cli("block_tech_shift_reservations", ["--days-ahead", "1", "--no-apply"])
    
    # Verify no new blackouts needed (already exists)
    assert len(result) == 1
    summary = result[0]
    assert summary["blackouts_needed"] == 0
    assert not mock_create.called
