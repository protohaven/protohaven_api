# pylint: skip-file
from protohaven_api.automation.policy import enforcer as e
from protohaven_api.commands import violations as v


def test_enforce_policies_no_output(mocker, capsys):
    """Confirm that when there are no violations, we send no notifications"""
    mocker.patch.object(v.airtable, "get_policy_violations", return_value=[])
    mocker.patch.object(v.airtable, "get_policy_fees", return_value=[])
    mocker.patch.object(e.airtable, "get_policy_sections", return_value=[])
    mocker.patch.object(v.enforcer, "gen_fees", return_value=[])
    mocker.patch.object(v.enforcer, "gen_suspensions", return_value=[])
    v.Commands().enforce_policies(["--apply"])
    captured = capsys.readouterr()
    assert captured.out.strip() == "[]"
