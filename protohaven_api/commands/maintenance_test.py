"""Testing of maintenance commands"""
import yaml

from protohaven_api.commands import maintenance as m


def test_gen_maintenance_tasks(mocker, capsys):
    """Confirm generation of maintenance tasks summary"""
    mocker.patch.object(
        m.manager,
        "run_daily_maintenance",
        return_value=[{"gid": "123", "name": "test task"}],
    )
    m.Commands.gen_maintenance_tasks("/asdf/ghjk", ["--apply"])
    got = yaml.safe_load(capsys.readouterr().out)
    assert len(got) == 1
    assert "[test task](https://app.asana.com/0/1202469740885594/123)" in got[0]["body"]


def test_tech_leads_maintenance_none(mocker, capsys):
    """Confirm that when there are no stale tasks, we send no notifications"""
    mocker.patch.object(m.manager, "get_stale_tech_ready_tasks", return_value=[])
    m.Commands.gen_tech_leads_maintenance_summary("/asdf/ghjk", [])
    captured = capsys.readouterr()
    assert captured.out.strip() == "[]"
