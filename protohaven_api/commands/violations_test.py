"""Test violations commands"""

import pytest

from protohaven_api.automation.policy import enforcer as e
from protohaven_api.commands import violations as v
from protohaven_api.testing import mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create CLI fixture"""
    return mkcli(capsys, v)


def test_enforce_policies_no_output(mocker, cli):
    """Confirm that when there are no violations, we send no notifications"""
    mocker.patch.object(v.airtable, "get_policy_violations", return_value=[])
    mocker.patch.object(v.airtable, "get_policy_fees", return_value=[])
    mocker.patch.object(e.airtable, "get_policy_sections", return_value=[])
    mocker.patch.object(v.enforcer, "gen_fees", return_value=[])
    assert cli("enforce_policies", ["--apply"]) == []


def test_enforce_policies_no_apply_skips_accruals(mocker, cli):
    """--no-apply must not mutate violation accrual totals."""
    mocker.patch.object(v.airtable, "get_policy_violations", return_value=[])
    mocker.patch.object(v.airtable, "get_policy_fees", return_value=[])
    mocker.patch.object(e.airtable, "get_policy_sections", return_value=[])
    mocker.patch.object(v.enforcer, "gen_fees", return_value=[])
    update_accruals = mocker.patch.object(v.enforcer, "update_accruals")
    assert cli("enforce_policies", ["--no-apply"]) == []
    update_accruals.assert_not_called()


def test_enforce_policies_filter_restricts_to_requested_violations(mocker, cli):
    """--filter must only process the requested violation IDs."""
    violations = [{"id": "keep", "fields": {}}, {"id": "drop", "fields": {}}]
    mocker.patch.object(v.airtable, "get_policy_violations", return_value=violations)
    fees = []
    mocker.patch.object(v.airtable, "get_policy_fees", return_value=fees)
    mocker.patch.object(e.airtable, "get_policy_sections", return_value=[])
    gen_fees = mocker.patch.object(v.enforcer, "gen_fees", return_value=[])
    gen_comms = mocker.patch.object(v.enforcer, "gen_comms", return_value=[])
    update_accruals = mocker.patch.object(v.enforcer, "update_accruals")

    cli("enforce_policies", ["--apply", "--filter=keep"])

    gen_fees.assert_called_once_with([{"id": "keep", "fields": {}}])
    gen_comms.assert_called_once_with([{"id": "keep", "fields": {}}], [], [])
    update_accruals.assert_called_once_with([])
