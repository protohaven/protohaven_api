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
