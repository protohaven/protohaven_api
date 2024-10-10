"""Testing of maintenance commands"""
import pytest

from protohaven_api.commands import maintenance as m
from protohaven_api.testing import MatchStr, mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create cli test fixture for maintenance commands"""
    return mkcli(capsys, m)


def test_gen_maintenance_tasks(mocker, cli):
    """Confirm generation of maintenance tasks summary"""
    mocker.patch.object(
        m.manager,
        "run_daily_maintenance",
        return_value=[{"gid": "123", "name": "test task"}],
    )
    got = cli("gen_maintenance_tasks", ["--apply"])
    assert len(got) == 1
    assert "[test task](https://app.asana.com/0/1202469740885594/123)" in got[0]["body"]


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
