"""Tests for development CLI commands"""

import pickle

import pytest

from protohaven_api.commands import development as dev
from protohaven_api.testing import d, mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create CLI fixture"""
    return mkcli(capsys, dev)


def test_gen_mock_data(mocker, tmp_path, cli):
    """Test `gen_mock_data` command"""
    mocker.patch.object(dev.Commands, "_fetch_neon_accounts", return_value=([], []))
    mocker.patch.object(dev.Commands, "_fetch_airtable", return_value=[])
    mocker.patch.object(dev.Commands, "_fetch_neon_events", return_value=([], []))
    mocker.patch.object(dev.neon, "fetch_clearance_codes", return_value=[])
    cli(
        "gen_mock_data",
        ["--path", str(tmp_path / "test.pkl"), "--after", d(0).isoformat()],
    )
    with open(str(tmp_path / "test.pkl"), "rb") as f:
        got = pickle.load(f)
    assert isinstance(got, dict)
