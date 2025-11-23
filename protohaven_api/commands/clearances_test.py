"""Test of clearance CLI commands"""

from collections import namedtuple

import pytest

from protohaven_api.commands import clearances as C
from protohaven_api.testing import d, idfn, mkcli


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


def test_recertification_no_work(mocker, cli):
    """Test recertification command when no work needs to be done"""
    mocker.patch.object(C, "build_recert_env")
    mocker.patch.object(C, "segment_by_recertification_needed", return_value=([], []))
    mocker.patch.object(C.airtable, "get_pending_recertifications", return_value=[])

    out = cli("recertification", [])
    assert not out


Tc = namedtuple(
    "tc",
    "desc,has_clearance,is_pending,is_due,recert_needed,want_insert,want_remove,want_mod",
)


@pytest.mark.parametrize(
    "tc",
    [
        Tc(
            "user with clearance newly pending, adds to pending w/ no clearance change",
            has_clearance=False,  # even if they don't actually have the clearance
            recert_needed=True,
            is_pending=False,
            is_due=False,
            want_insert=True,
            want_remove=False,
            want_mod=None,
        ),
        Tc(
            "no-op if already pending and not yet due",
            has_clearance=True,
            recert_needed=True,
            is_pending=True,
            is_due=False,
            want_insert=False,
            want_remove=False,
            want_mod=None,
        ),
        Tc(
            "if recertified before due, removes from pending (no clearance addition)",
            has_clearance=True,
            recert_needed=False,
            is_pending=True,
            is_due=False,
            want_insert=False,
            want_remove=True,
            want_mod=None,
        ),
        Tc(
            "warned user, due recert, revokes clearance and stays in pending list",
            has_clearance=True,
            recert_needed=True,
            is_pending=True,
            is_due=True,
            want_insert=False,
            want_remove=False,
            want_mod="DELETE",
        ),
        Tc(
            "past-due member does not continue to be modified",
            has_clearance=False,
            recert_needed=True,
            is_pending=True,
            is_due=True,
            want_insert=False,
            want_remove=False,
            want_mod=None,
        ),
        Tc(
            "if recertified, adds missing clearance and removes from pending",
            has_clearance=False,
            recert_needed=False,
            is_pending=True,
            is_due=False,
            want_insert=False,
            want_remove=True,
            want_mod="PATCH",
        ),
    ],
    ids=idfn,
)
def test_recertification_e2e(mocker, cli, tc):
    """Test recertification command adding pending recerts and removing clearances"""
    mocker.patch.object(C, "tznow", return_value=d(0, 12))
    mock_env = mocker.MagicMock(
        neon_clearances={
            "user": ["tool"] if tc.has_clearance else [],
        }
    )
    mocker.patch.object(C.clearances, "build_recert_env", return_value=mock_env)
    needed = [("user", "tool")] if tc.recert_needed else []
    not_needed = [("user", "tool")] if not tc.recert_needed else []
    mocker.patch.object(
        C.clearances,
        "segment_by_recertification_needed",
        return_value=(needed, not_needed),
    )

    pending = (
        [("user", "tool", d(0) if tc.is_due else d(1), "rec123")]
        if tc.is_pending
        else []
    )
    mocker.patch.object(
        C.airtable, "get_pending_recertifications", return_value=pending
    )

    mock_mod = mocker.patch.object(
        C.clearances, "update_by_neon_id", return_value=["tool"]
    )
    mock_insert = mocker.patch.object(C.airtable, "insert_pending_recertification")
    mock_remove = mocker.patch.object(C.airtable, "remove_pending_recertification")

    got = cli("recertification", ["--apply"])
    if tc.want_insert:
        mock_insert.assert_called_once_with("user", "tool", mocker.ANY)
    if tc.want_remove:
        mock_remove.assert_called_once_with("rec123")
    if tc.want_mod:
        mock_mod.assert_called_with("user", tc.want_mod, ["tool"], apply=True)
    else:
        mock_mod.assert_not_called()

    # Verify messages sent
    assert len(got) == (1 if (tc.want_insert or tc.want_remove or tc.want_mod) else 0)
