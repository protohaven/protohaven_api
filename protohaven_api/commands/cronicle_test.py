"""Tests for Cronicle CLI commands."""

# pylint: disable=missing-function-docstring

import pytest

from protohaven_api.commands import cronicle as C
from protohaven_api.testing import d, mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    return mkcli(capsys, C)


def test_backup_cronicle_tars_and_uploads(mocker, cli):
    mocker.patch.object(C, "tznow", return_value=d(0))
    mocker.patch.object(C, "get_config", return_value="https://cron.example.com")
    mocker.patch.object(C, "CronicleClient")
    schedule_backup = mocker.patch.object(C, "schedule_backup", return_value=1024)
    mock_upload = mocker.patch.object(C.drive, "upload_file", return_value="fileid")

    got = cli("backup_cronicle", ["--parent_id=test_parent_id", "--api_key=key"])

    C.CronicleClient.assert_called_once_with(  # pylint: disable=no-member
        "https://cron.example.com", "key"
    )
    schedule_backup.assert_called_once()
    mock_upload.assert_called_once()
    assert "test_parent_id" in got[0]["body"]


def test_backup_cronicle_dry_run_does_not_upload(mocker, cli):
    mocker.patch.object(C, "tznow", return_value=d(0))
    mocker.patch.object(C, "get_config", return_value="https://cron.example.com")
    mocker.patch.object(C, "CronicleClient")
    mocker.patch.object(C, "schedule_backup", return_value=1024)
    mock_upload = mocker.patch.object(C.drive, "upload_file")

    got = cli(
        "backup_cronicle",
        ["--parent_id=test_parent_id", "--api_key=key", "--no-apply"],
    )

    mock_upload.assert_not_called()
    assert "DRY_RUN" in got[0]["body"]
