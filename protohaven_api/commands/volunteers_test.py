"""Tests for volunteers CLI commands"""

from collections import namedtuple

import pytest

from protohaven_api.commands import volunteers as E
from protohaven_api.testing import d, idfn, mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create cli() test function"""
    return mkcli(capsys, E)


def _make_day(date_str, is_holiday, am_people, pm_people):
    """Helper to build a calendar_view day dict"""
    return {
        "date": date_str,
        "is_holiday": is_holiday,
        "AM": {
            "id": f"Badge{date_str}AM",
            "title": f"{date_str} AM",
            "people": am_people,
            "color": "danger" if not am_people else "success",
        },
        "PM": {
            "id": f"Badge{date_str}PM",
            "title": f"{date_str} PM",
            "people": pm_people,
            "color": "danger" if not pm_people else "success",
        },
    }


Tc = namedtuple("TC", "desc,days_ahead,calendar_view,want_targets,want_subjects")


@pytest.mark.parametrize(
    "tc",
    [
        Tc(
            "no empty shifts",
            14,
            [
                _make_day("2025-01-01", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-02", False, ["tech1"], ["tech2"]),
            ],
            [],
            [],
        ),
        Tc(
            "empty shift 7+ days away -> #tech-leads",
            14,
            [
                _make_day("2025-01-01", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-02", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-03", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-04", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-05", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-06", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-07", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-08", False, [], ["tech2"]),
            ],
            ["#tech-leads"],
            ["have no techs"],
        ),
        Tc(
            "empty shift <= 3 days away -> #techs",
            14,
            [
                _make_day("2025-01-01", False, [], ["tech2"]),
                _make_day("2025-01-02", False, ["tech1"], []),
            ],
            ["#techs", "#techs"],
            ["with nobody on duty", "with nobody on duty"],
        ),
        Tc(
            "holiday with no techs is skipped",
            14,
            [
                _make_day("2025-01-01", True, [], []),
                _make_day("2025-01-02", False, ["tech1"], ["tech2"]),
            ],
            [],
            [],
        ),
        Tc(
            "empty shift 4-6 days away generates no alert",
            14,
            [
                _make_day("2025-01-01", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-02", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-03", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-04", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-05", False, [], ["tech2"]),
            ],
            [],
            [],
        ),
        Tc(
            "mixed: leads and techs alerts",
            14,
            [
                _make_day("2025-01-01", False, [], ["tech2"]),  # day 0 -> #techs
                _make_day("2025-01-02", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-03", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-04", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-05", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-06", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-07", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-08", False, [], ["tech2"]),  # day 7 -> #tech-leads
            ],
            ["#techs", "#tech-leads"],
            ["with nobody on duty", "have no techs"],
        ),
        Tc(
            "custom days_ahead limits range",
            3,
            [
                _make_day("2025-01-01", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-02", False, ["tech1"], ["tech2"]),
                _make_day("2025-01-03", False, ["tech1"], ["tech2"]),
            ],
            [],
            [],
        ),
    ],
    ids=idfn,
)
def test_check_empty_shifts(mocker, tc, cli):
    """Test behavior of check_empty_shifts CLI command"""
    mocker.patch.object(E, "tznow", return_value=d(0))
    mocker.patch.object(
        E.forecast,
        "generate",
        return_value={"calendar_view": tc.calendar_view},
    )
    got = cli("check_empty_shifts", ["--days-ahead", str(tc.days_ahead)])

    targets = [g["target"] for g in got]
    assert targets == list(tc.want_targets)

    # Each message must have a unique id for deduplication
    msg_ids = [g["id"] for g in got]
    assert len(msg_ids) == len(set(msg_ids)), f"Duplicate message ids: {msg_ids}"

    for i, want_subject in enumerate(tc.want_subjects):
        assert want_subject in got[i]["subject"]


def test_check_empty_shifts_default_days_ahead(mocker, cli):
    """Test that default --days-ahead is 14"""
    mocker.patch.object(E, "tznow", return_value=d(0))
    mock_gen = mocker.patch.object(
        E.forecast,
        "generate",
        return_value={"calendar_view": []},
    )
    cli("check_empty_shifts", [])
    mock_gen.assert_called_once_with(d(0), 14, include_pii=False)
