"""Tests for validation module"""
from collections import namedtuple

import pytest

from protohaven_api.class_automation import validation as v
from protohaven_api.class_automation.solver import Class
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


Tc = namedtuple("tc", "desc,t0,inst_occupancy,area_occupancy,want_reason")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("pass, simple", d(1), [], {}, None),
        Tc(
            "fail, holiday", d(0, 14), [], {}, "Occurs on a US holiday"
        ),  # Jan 1, 2025 i.e. new years' day
        Tc(
            "fail, instructor occupied that day",
            d(1, 12),
            [[d(1, 16), d(1, 19), "Other Class"]],
            {},
            "Same day as another class being taught by instructor (Other Class)",
        ),
        Tc(
            "fail, area overlap",
            d(1, 18),
            [],
            {"a0": [[d(1, 18), d(1, 19), "Occupying Event"]]},
            "Area already occupied by other event (Occupying Event)",
        ),
        Tc(
            "fail, too soon",
            d(6),
            [],
            {},
            "Too soon before/after same class (scheduled for 2025-01-08; "
            "no repeats allowed between 2025-01-06 and 2025-01-11)",
        ),
        Tc(
            "pass, complex",
            d(4, 18),
            [[d(3, 18), d(3, 21), "Other Class"]],
            {"a0": [[d(3, 18), d(3, 21), "Occupying Event"]]},
            None,
        ),
    ],
    ids=idfn,
)
def test_validate_candidate_class_time(tc):
    """Test cases for validate_candidate_class_time"""
    testclass = Class(
        "test_id",
        "Test Class",
        3,
        areas=["a0"],
        exclusions=[[d(5), d(10), d(7)]],
        score=1.0,
    )
    valid, reason = v.validate_candidate_class_time(
        testclass, tc.t0, tc.inst_occupancy, tc.area_occupancy
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
        Tc("Simple containment", d(0, 12), [(d(0), d(1), "foo")], [d(0), d(1), "foo"]),
        Tc("Too late", d(2), [(d(0), d(1), "foo")], False),
        Tc("Too early", d(-1), [(d(0), d(1), "foo")], False),
    ],
    ids=idfn,
)
def test_date_within_exclusions(tc):
    """Verify behavior of date math in date_within_exclusions"""
    assert v.date_within_exclusions(tc.d, tc.exclusions) == tc.want


Tc = namedtuple("TC", "desc,dd,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("Empty case", [], []),
        Tc("Base case", [("a", d(0, 12), d(0, 13))], [("a", d(0, 12), d(0, 13))]),
        Tc(
            "Simple merge",
            [("a", d(0, 12), d(0, 14)), ("b", d(0, 13), d(0, 15))],
            [("a", d(0, 12), d(0, 15))],
        ),
        Tc(
            "Duplicate merge",
            [("a", d(0, 12), d(0, 14)), ("b", d(0, 12), d(0, 14))],
            [("a", d(0, 12), d(0, 14))],
        ),
        Tc(
            "Merge does not affect next date if separate",
            [
                ("a", d(0, 12), d(0, 13)),
                ("b", d(0, 12), d(0, 14)),
                ("c", d(0, 14), d(0, 15)),
            ],
            [("a", d(0, 12), d(0, 14)), ("c", d(0, 14), d(0, 15))],
        ),
    ],
    ids=idfn,
)
def test_sort_and_merge_date_ranges(tc):
    """Test cases for sort_and_merge_date_ranges function"""
    assert list(v.sort_and_merge_date_ranges(tc.dd)) == tc.want
