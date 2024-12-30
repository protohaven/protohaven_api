"""Testing of maintenance commands"""

import pytest

from protohaven_api.commands import maintenance as m
from protohaven_api.testing import MatchStr, d, mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create cli test fixture for maintenance commands"""
    return mkcli(capsys, m)


def test_gen_maintenance_tasks(mocker, cli):
    """Confirm generation of maintenance tasks summary"""
    mocker.patch.object(
        m.manager,
        "get_maintenance_needed_tasks",
        return_value=[
            {
                "id": "rec345",
                "section": "foo",
                "name": "test task",
                "detail": "details",
                "tags": ["tech_ready"],
                "next_schedule": d(1),
            }
        ],
    )
    mocker.patch.object(
        m.tasks, "add_maintenance_task_if_not_exists", return_value="123"
    )
    mocker.patch.object(m.comms, "send_discord_message")
    got = cli("gen_maintenance_tasks", ["--apply"])
    assert len(got) == 1
    assert "[test task](https://app.asana.com/0/1202469740885594/123)" in got[0]["body"]
    m.comms.send_discord_message.assert_not_called()  # pylint: disable=no-member


def test_gen_maintenance_tasks_corrupted(mocker, cli):
    """Confirm generation of maintenance tasks even if one has bad data"""
    mocker.patch.object(
        m.manager,
        "get_maintenance_needed_tasks",
        return_value=[
            {
                "id": "rec345",
                "section": "foo",
                "name": "test task",
                "tags": ["tech_ready"],
                # Note no details section
                "next_schedule": d(1),
            }
        ],
    )
    mocker.patch.object(
        m.tasks, "add_maintenance_task_if_not_exists", return_value="123"
    )
    mocker.patch.object(m.comms, "send_discord_message")
    got = cli("gen_maintenance_tasks", ["--apply"])
    assert len(got) == 1
    assert "no new tasks" in got[0]["body"]
    m.comms.send_discord_message.assert_called_once()  # pylint: disable=no-member


def test_tech_leads_maintenance_none(mocker, cli):
    """Confirm that when there are no stale tasks, we send no notifications"""
    mocker.patch.object(m.manager, "get_stale_tech_ready_tasks", return_value=[])
    assert cli("gen_tech_leads_maintenance_summary", []) == []


def test_tech_leads_maintenance_sends(mocker, cli):
    """Confirm that when there are no stale tasks, we send no notifications"""
    mocker.patch.object(
        m.manager,
        "get_stale_tech_ready_tasks",
        return_value=[
            {"name": "Task 1", "gid": "123", "days_ago": 5},
            {"name": "Task 2", "gid": "456", "days_ago": 10},
        ],
    )
    expected = [
        {
            "subject": "Stale maintenance tasks",
            "body": MatchStr("2 tech_ready tasks"),
            "target": "#tech-leads",
            "id": "daily_maintenance",
        }
    ]
    assert cli("gen_tech_leads_maintenance_summary", []) == expected


def test_check_door_sensors(mocker, cli):
    """Test check_door_sensors command for doors configured and closed"""
    mocker.patch.object(m, "get_config", return_value=["Front Door", "Back Door"])
    mocker.patch.object(m.wyze, "init")
    mocker.patch.object(
        m.wyze,
        "get_door_states",
        return_value=[
            {"name": "Front Door", "is_online": True, "open_close_state": True},
            {"name": "Back Door", "is_online": True, "open_close_state": True},
        ],
    )
    assert not cli("check_door_sensors", [])


def test_check_door_sensors_with_warnings(mocker, cli):
    """Test check_door_sensors command with warnings"""
    mocker.patch.object(m, "get_config", return_value=["Front Door", "Garage Door"])
    mocker.patch.object(m.wyze, "init")
    mocker.patch.object(
        m.wyze,
        "get_door_states",
        return_value=[
            {"name": "Front Door", "is_online": False, "open_close_state": True},
            {"name": "Back Door", "is_online": True, "open_close_state": False},
        ],
    )
    got = cli("check_door_sensors", [])
    assert len(got) == 1
    assert (
        "Door(s) {'Back Door'} configured in Wyze, but not in protohaven_api config.yaml"
        in got[0]["body"]
    )
    assert (
        "Door(s) {'Garage Door'} expected per protohaven_api config.yaml, but not present in Wyze"
        in got[0]["body"]
    )
    assert (
        "Door Front Door offline; check battery and/or [Wyze Sense Hub]"
        in got[0]["body"]
    )
    assert "**IMPORTANT**: Door Back Door is open" in got[0]["body"]


def test_check_cameras(mocker, cli):
    """Test the check_cameras command with mocked dependencies."""
    mocker.patch.object(m, "get_config", return_value={"Camera1", "Camera2"})
    mock_camera_states = [
        {"name": "Camera1", "is_online": True},
        {"name": "Camera3", "is_online": False},
    ]
    mocker.patch.object(m.wyze, "init")
    mocker.patch.object(m.wyze, "get_camera_states", return_value=mock_camera_states)
    got = cli("check_cameras", [])
    for expected in [
        "Camera(s) {'Camera3'} configured in Wyze, but not in protohaven_api config.yaml",
        "Camera {'Camera2'} expected per protohaven_api config.yaml, but not present in Wyze",
        "camera Camera3 offline (check power cable/network connection)",
    ]:
        assert expected in got[0]["body"]


def test_backup_wiki(mocker, cli):
    """Test backing up with mocked actions"""
    mocker.patch.object(m, "tznow", return_value=d(0))
    mocker.patch.object(m.wiki, "fetch_db_backup", return_value=1024)
    mocker.patch.object(m.wiki, "fetch_files_backup", return_value=2048)
    mock_do_backup = mocker.patch.object(m.drive, "upload_file", return_value="fileid")

    args = mocker.Mock()
    args.parent_id = "test_parent_id"

    got = cli("backup_wiki", ["--parent_id=test_parent_id"])

    assert mock_do_backup.call_count == 2
    assert "test_parent_id" in got[0]["body"]
