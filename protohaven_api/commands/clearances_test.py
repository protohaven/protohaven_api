"""Test of clearance CLI commands"""

import pytest

from protohaven_api.commands import clearances as C
from protohaven_api.testing import d, mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create cli() test function"""
    return mkcli(capsys, C)


def test_sync_clearances_no_submissions(mocker, cli):
    """Test sync_clearances without applying changes"""
    mocker.patch.object(
        C.neon, "fetch_clearance_codes", return_value=[{"name": "code1"}]
    )
    mocker.patch.object(C.sheets, "get_passing_student_clearances", return_value=[])
    got = cli("sync_clearances", [])
    assert not got


def test_sync_clearances_e2e(mocker, cli):
    """Test sync_clearances with applying changes"""
    mocker.patch.object(
        C.neon,
        "fetch_clearance_codes",
        return_value=[
            {"name": c} for c in ("code1_resolved", "code2_resolved", "tool1", "tool2")
        ],
    )
    mocker.patch.object(C, "tznow", return_value=d(0))
    mocker.patch.object(
        C.sheets,
        "get_passing_student_clearances",
        return_value=[
            (
                "test@example.com",
                ["code1", "code2"],
                ["tool1", "tool2"],
            )
        ],
    )
    mocker.patch.object(
        C.clearances, "resolve_codes", lambda tc: [t + "_resolved" for t in tc]
    )
    m1 = mocker.patch.object(C.clearances, "update", return_value=["code1"])
    got = cli("sync_clearances", ["--apply"])
    m1.assert_called_with(
        "test@example.com",
        "PATCH",
        {"code1_resolved", "code2_resolved", "tool1", "tool2"},
        apply=True,
    )
    assert len(got) == 1
    assert "test@example.com: added code1" in got[0]["body"]
