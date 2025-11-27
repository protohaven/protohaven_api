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
    mocker.patch.object(C.clearances, "build_recert_env")
    mocker.patch.object(
        C.clearances, "segment_by_recertification_needed", return_value=({}, {})
    )
    mocker.patch.object(C.airtable, "get_pending_recertifications", return_value=[])
    mocker.patch.object(C.airtable, "get_tools", return_value=[])

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
            "User needs no clearance, none pending or due -> no action",
            has_clearance=False,
            recert_needed=False,
            is_pending=False,
            is_due=False,
            want_insert=False,
            want_remove=False,
            want_mod=None,
        ),
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
            # Note: adding clearances is done via other automation
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
    ],
    ids=idfn,
)
def test_recertification_e2e(mocker, cli, tc):
    """Test recertification command adding pending recerts and removing clearances"""
    mocker.patch.object(C, "tznow", return_value=d(0, 12))
    mock_env = mocker.MagicMock(
        neon_clearances={
            "user": ["tool"] if tc.has_clearance else [],
        },
        contact_info={
            "user": ("User", "user@example.com"),
        },
    )
    mocker.patch.object(C.clearances, "build_recert_env", return_value=mock_env)
    deadline = d(0) if tc.is_due else d(1)
    needed = {("user", "tool"): (deadline, deadline)} if tc.recert_needed else {}
    not_needed = (
        {("user", "tool"): (deadline, deadline)} if not tc.recert_needed else {}
    )
    mocker.patch.object(
        C.clearances,
        "segment_by_recertification_needed",
        return_value=(needed, not_needed),
    )

    pending = [("user", "tool", deadline, deadline, "rec123")] if tc.is_pending else []
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
        mock_insert.assert_called_once_with("user", "tool", mocker.ANY, mocker.ANY)
    if tc.want_remove:
        mock_remove.assert_called_once_with("rec123")
    if tc.want_mod:
        mock_mod.assert_called_with("user", tc.want_mod, ["tool"], apply=True)
    else:
        mock_mod.assert_not_called()

    # Verify messages sent
    assert len(got) == (1 if (tc.want_insert or tc.want_remove or tc.want_mod) else 0)


def test_recertifaction_max_affected(mocker, cli):
    """Verify that --max_users_affected is properly observed"""
    mocker.patch.object(C.clearances, "build_recert_env")
    mocker.patch.object(
        C.clearances, "segment_by_recertification_needed", return_value=({}, {})
    )
    mocker.patch.object(C.airtable, "get_pending_recertifications", return_value=[])
    mocker.patch.object(C.airtable, "get_tools", return_value=[])
    mocker.patch.object(
        C.Commands,
        "_stage_revoke_due_clearances",
        return_value={i: [(f"C{i}", None)] for i in range(10)},
    )

    mock_mod = mocker.patch.object(
        C.clearances, "update_by_neon_id", return_value=["tool"]
    )

    cli("recertification", ["--apply", "--max_users_affected=4"])
    assert mock_mod.call_count == 4


def test_recertifaction_filter_users(mocker, cli):
    """Verify that --filter_users is properly observed"""
    mocker.patch.object(C.clearances, "build_recert_env")
    mocker.patch.object(
        C.clearances, "segment_by_recertification_needed", return_value=({}, {})
    )
    mocker.patch.object(C.airtable, "get_pending_recertifications", return_value=[])
    mocker.patch.object(C.airtable, "get_tools", return_value=[])
    mocker.patch.object(
        C.Commands,
        "_stage_revoke_due_clearances",
        return_value={i: [(f"C{i}", None)] for i in range(10)},
    )

    mock_mod = mocker.patch.object(
        C.clearances, "update_by_neon_id", return_value=["tool"]
    )

    cli("recertification", ["--apply", "--filter_users=0,2"])
    assert sorted([c.args[0] for c in mock_mod.mock_calls]) == [0, 2]


def test_tidy_recertification_table_updates_deadlines(mocker):
    """Test that e updates deadlines when they change"""
    mock_pending = {
        (123, "LATHE"): ("rec_abc", d(0), d(1)),
        (456, "MILL"): ("rec_def", d(2), d(3)),
    }
    mock_needed = {(123, "LATHE"): (d(0), d(2)), (456, "MILL"): (d(2), d(3))}

    mock_update = mocker.patch.object(
        C.airtable, "update_pending_recertification", return_value="updated"
    )

    C.Commands.tidy_recertification_table(mock_pending, mock_needed)

    mock_update.assert_called_once_with("rec_abc", d(0), d(2))
