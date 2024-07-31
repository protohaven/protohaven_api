"""Test behavior of linear solver for class scheduling"""
import datetime
from collections import namedtuple

import pytest

from protohaven_api.class_automation import solver as s  # pylint: disable=import-error


def idfn(tc):
    """Extract description from named tuple for parameterization"""
    return tc.desc


def d(i, h=0):
    """Returns a date based on an integer, for testing"""
    return datetime.datetime(year=2025, month=1, day=1) + datetime.timedelta(
        days=i, hours=h
    )


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
    assert s.has_area_conflict(tc.area_occupancy, tc.t_start, tc.t_end) == tc.want


Tc2 = namedtuple("TC", "desc,d,exclusions,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc2("Simple containment", d(0, 12), [(d(0), d(1), "foo")], "foo"),
        Tc2("Too late", d(2), [(d(0), d(1), "foo")], False),
        Tc2("Too early", d(-1), [(d(0), d(1), "foo")], False),
    ],
    ids=idfn,
)
def test_date_within_exclusions(tc):
    """Verify behavior of date math in date_within_exclusions"""
    assert s.date_within_exclusions(tc.d, tc.exclusions) == tc.want


def test_solve_simple():
    """An instructor can schedule a class at a time"""
    got, score, _ = s.solve(
        classes=[s.Class(1, "Embroidery", 1, ["textiles"], [], 0.7)],
        instructors=[s.Instructor("A", [1], [d(0)])],
        area_occupancy={},
    )
    assert got == {"A": [[1, "Embroidery", "2025-01-01T00:00:00"]]}
    assert score == 0.7


def test_solve_complex():
    """Run an example set of classes and instructors through the solver; assert no exceptions"""
    classes = [
        s.Class(*v)
        for v in [
            (1, "Embroidery", 1, ["textiles"], [], 0.7),
            (2, "Sewing Basics", 2, ["textiles"], [], 0.6),
            (3, "Basic Woodshop", 2, ["wood"], [], 0.5),
            (4, "Millwork", 1, ["wood"], [], 0.7),
            (5, "Basic Metals", 2, ["metal"], [], 0.8),
            (6, "Metal Workshop", 1, ["metal"], [], 0.4),
        ]
    ]

    people = [
        s.Instructor(*v)
        for v in [
            ("A", [1, 2], [d(i) for i in [1, 7, 14, 21, 29]]),
            (
                "B",
                [3, 1, 4],
                [d(i) for i in [1, 4, 5, 8, 11, 14, 22, 25, 29]],
            ),
            ("C", [5, 6, 1], [d(i) for i in [5, 7, 2, 1]]),
            ("D", [4, 2], [d(i) for i in range(30)]),
        ]
    ]

    area_occupancy = {}
    s.solve(classes, people, area_occupancy)


def test_solve_no_area_overlap():
    """When an instructor attempts to schedule a class, the solver prefers
    not offering the class instead of scheduling it in an occupied area"""
    pd = (d(1), d(1, 3), "pd")
    got, score, skips = s.solve(
        classes=[s.Class(1, "Embroidery", 1, ["textiles"], [], 0.7)],
        instructors=[s.Instructor("A", [1], [pd[0]])],
        area_occupancy={"textiles": [pd]},
    )
    assert not got
    assert score == 0
    assert skips == {
        "a": {"Area already occupied by other class": [(d(1), d(1), "pd")]}
    }


def test_solve_exclusion():
    """When an instructor attempts to schedule a class, the solver prefers not
    offering the class instead of running it in an exclusion region"""
    c = s.Class(1, "Embroidery", 1, ["textiles"], [[d(-2), d(2), d(0)]], 0.7)
    got, score, skips = s.solve(
        classes=[c],
        instructors=[s.Instructor("A", [1], [d(1)])],
        area_occupancy={},
    )
    assert not got
    assert score == 0
    assert skips == {
        "a": {"Too soon before/after same class": [(d(1), d(0), "Embroidery")]}
    }


def test_solve_no_concurrent_overlap():
    """Verify classes do not overlap the same area at the same time
    when scheduled concurrently. Higher score classes win."""
    got, score, _ = s.solve(
        classes=[
            s.Class(1, "Embroidery", 1, ["textiles"], [], 0.7),
            s.Class(2, "Embroidery but cooler", 1, ["textiles"], [], 0.8),
        ],
        instructors=[
            s.Instructor("A", [1], [d(0)]),
            s.Instructor("B", [2], [d(0)]),
        ],
        area_occupancy={},
    )
    assert got == {"B": [[2, "Embroidery but cooler", "2025-01-01T00:00:00"]]}
    assert score == 0.8


def test_solve_no_double_booking():
    """An instructor should only be scheduled one class at a given time.
    Higher score classes should be preferred"""
    got, score, _ = s.solve(
        classes=[
            s.Class(1, "Embroidery", 1, ["textiles"], [], 0.7),
            s.Class(2, "Lasers", 1, ["lasers"], [], 0.8),
        ],
        instructors=[
            s.Instructor("A", [1, 2], [d(0)]),
        ],
        area_occupancy={},
    )
    assert got == {"A": [[2, "Lasers", "2025-01-01T00:00:00"]]}
    assert score == 0.8


def test_solve_at_most_once():
    """Classes run at most once per run of the solver"""
    got, score, _ = s.solve(
        classes=[
            s.Class(1, "Embroidery", 1, ["textiles"], [], 0.7),
        ],
        instructors=[
            s.Instructor("A", [1], [d(0)]),
            s.Instructor("B", [1], [d(1)]),
        ],
        area_occupancy={},
    )
    assert got == {"A": [[1, "Embroidery", "2025-01-01T00:00:00"]]}
    assert score == 0.7
