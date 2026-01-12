"""Tests for validation module"""

from collections import namedtuple

import pytest

from protohaven_api.automation.classes import validation as v
from protohaven_api.testing import d, idfn

Tc = namedtuple("tc", "desc,a0,a1,b0,b1,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("no overlap", d(0), d(1), d(2), d(3), False),
        Tc("next to each other", d(0), d(1), d(1), d(2), False),
        Tc("a end > b start", d(0), d(2), d(1), d(3), True),
        Tc("a encloses b", d(0), d(3), d(1), d(2), True),
        Tc("a == b", d(0), d(1), d(0), d(1), True),
        Tc("same start", d(0), d(1), d(0), d(2), True),
        Tc("same end", d(0), d(2), d(1), d(2), True),
    ],
    ids=idfn,
)
def test_date_range_overlaps(tc):
    """Test date range overlaps returns proper responses, also automatically
    testing the symmetric case (where `a` and `b` are swapped)
    """
    assert v.date_range_overlaps(tc.a0, tc.a1, tc.b0, tc.b1) == tc.want
    assert v.date_range_overlaps(tc.b0, tc.b1, tc.a0, tc.a1) == tc.want


fields = {
    "desc": None,
    "inst_occupancy": [],
    "area_occupancy": {},
    "exclusions": {
        "tc": [v.Exclusion(start=d(5), end=d(10), main_date=d(7), origin="for reasons")]
    },
    "interval": (d(3, 16), d(3, 19)),
    "want_reason": None,
    "class_hours": [3],
}
Tc = namedtuple("tc", tuple(fields.keys()), defaults=tuple(fields.values()))


@pytest.mark.parametrize(
    "tc",
    [
        Tc("pass, simple"),
        Tc(
            "fail, holiday",
            interval=(d(0, 14), d(0, 17)),
            want_reason="Occurs on a US holiday (New Year's Day)",
        ),  # Jan 1, 2025 i.e. new years' day
        Tc(
            "hours mismatch",
            interval=(d(0, 14), d(0, 18)),  # 4h instead of 3h
            want_reason="duration is 4.0h, want 3h",
        ),
        Tc(
            "fail, instructor occupied that day",
            inst_occupancy=[(d(3, 12), d(3, 14), "Other Class")],
            want_reason="Same day as another class you're teaching (Other Class)",
        ),
        Tc(
            "fail, area overlap",
            area_occupancy={"a0": [(d(3, 16), d(3, 17), "Occupying Event")]},
            want_reason="Area a0 already occupied (Occupying Event)",
        ),
        Tc(
            "fail, too soon",
            interval=(d(5, 16), d(5, 19)),
            want_reason="Too soon before/after same for reasons (scheduled for 2025-01-08; "
            "no repeats allowed between 2025-01-06 and 2025-01-11)",
        ),
        Tc(
            "pass, complex",
            interval=(d(4, 18), d(4, 21)),
            inst_occupancy=[(d(3, 18), d(3, 21), "Other Class")],
            area_occupancy={"a0": [(d(3, 18), d(3, 21), "Occupying Event")]},
        ),
        Tc(
            "fail, end before start",
            interval=(d(4, 21), d(4, 18)),
            want_reason="End time 2025-01-05 18:00:00-05:00 must occur "
            "before start time 2025-01-05 21:00:00-05:00",
        ),
        Tc(
            "fail, start time in past",
            interval=(d(-1, 16), d(-1, 180)),
            want_reason="Start time 2024-12-31 16:00:00-05:00 is in the past",
        ),
    ],
    ids=idfn,
)
def test_validate_candidate_class_session(tc, mocker):
    """Test cases for validate_candidate_class_time"""
    env = v.ClassAreaEnv(
        clearance_exclusions={},
        area_occupancy=tc.area_occupancy,
        instructor_occupancy={"test_inst": tc.inst_occupancy},
        exclusions=tc.exclusions,
    )
    test_class = mocker.MagicMock(
        class_id="tc",
        name="Test Class",
        hours=tc.class_hours,
        areas=["a0"],
    )
    mocker.patch.object(v, "tznow", return_value=d(0, 12))
    valid, reason = v.validate_candidate_class_session(
        "test_inst", tc.interval, 0, test_class, env
    )
    if valid and tc.want_reason:
        raise RuntimeError(f"got valid; want invalid with reason {tc.want_reason}")
    if not valid:
        assert reason == tc.want_reason


Tc = namedtuple("TC", "desc,area_occupancy,t_start,t_end,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("Perfect overlap", [(d(0, 0), d(0, 3), "a")], d(0, 0), d(0, 3), "a"),
        Tc("Slightly before", [(d(0, 1), d(0, 4), "a")], d(0, 0), d(0, 3), "a"),
        Tc("Slightly after", [(d(0, 0), d(0, 3), "a")], d(0, 1), d(0, 4), "a"),
        Tc("Enclosed", [(d(0, 0), d(0, 3), "a")], d(0, 1), d(0, 2), "a"),
        Tc("Enclosing", [(d(0, 1), d(0, 2), "a")], d(0, 0), d(0, 3), "a"),
        Tc("Directly before", [(d(0, 3), d(0, 6), "a")], d(0, 0), d(0, 3), False),
        Tc("Directly after", [(d(0, 0), d(0, 3), "a")], d(0, 3), d(0, 6), False),
        Tc("Different day", [(d(1, 0), d(1, 3), "a")], d(0, 0), d(0, 3), False),
    ],
    ids=idfn,
)
def test_has_area_conflict(tc):
    """Verify behavior of date math in has_area_conflict"""
    assert v.has_area_conflict(tc.area_occupancy, tc.t_start, tc.t_end) == tc.want


Tc = namedtuple("TC", "desc,d,exclusions,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc(
            "Simple containment",
            d(0, 12),
            [(d(0), d(1), d(0, 12), "bar")],
            [d(0), d(1), d(0, 12), "bar"],
        ),
        Tc("Too late", d(2), [(d(0), d(1), d(0, 12), "bar")], False),
        Tc("Too early", d(-1), [(d(0), d(1), d(0, 12), "bar")], False),
    ],
    ids=idfn,
)
def test_date_within_exclusions(tc):
    """Verify behavior of date math in date_within_exclusions"""
    ee = [v.Exclusion(*e) for e in tc.exclusions]
    want = v.Exclusion(*tc.want) if tc.want else tc.want
    assert v.date_within_exclusions(tc.d, ee) == want
