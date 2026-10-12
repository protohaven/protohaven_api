"""Tests for Cronicle CLI commands."""

# pylint: disable=missing-function-docstring

import json

import pytest

from protohaven_api.commands import cronicle as C
from protohaven_api.testing import mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    return mkcli(capsys, C)


def test_backup_cronicle_emits_multijson(mocker, cli):
    rows = [
        {"id": "abc", "title": "Test event", "enabled": 1},
        {"id": "def", "title": "Other event", "enabled": 0},
    ]
    mock_client = mocker.patch.object(C, "CronicleClient").return_value
    mock_client.schedule.return_value = {"rows": rows}
    mocker.patch.object(
        C,
        "get_config",
        return_value="https://cron.example.com",
    )

    out = cli("backup_cronicle", ["--api_key", "key"], parse_yaml=False)

    C.CronicleClient.assert_called_once_with(  # pylint: disable=no-member
        "https://cron.example.com", "key"
    )
    assert [json.loads(line) for line in out.splitlines()] == rows
