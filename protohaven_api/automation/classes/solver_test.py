"""Test behavior of linear solver for class scheduling"""

from collections import namedtuple

import pytest

from protohaven_api.automation.classes import (
    solver as s,  # pylint: disable=import-error
)
from protohaven_api.testing import d, idfn

Tc = namedtuple("tc", "desc,t,a,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc(
            "basic",
            d(0),
            "textiles",
            [
                ("AE", d(0)),
                ("SB", d(0)),
            ],
        ),
        Tc(
            "prev runs also included",
            d(14),
            "textiles",
            [
                ("AE", d(0)),
                ("AE", d(7)),
                ("AE", d(14)),
                ("SB", d(14)),
            ],
        ),
    ],
    ids=idfn,
)
def test_class_starts_intersecting_time_and_area(tc):
    """Testing various scenarios of classes overlapping one another"""
    classes = [
        s.Class(cid, name, hours, days, areas, exclusions=[], score=1)
        for cid, name, hours, days, areas in [
            ("AE", "Advanced embroidery", 3, 3, ["textiles"]),
            ("SB", "Sewing Basics", 3, 1, ["textiles"]),
            ("BW", "Basic Woodshop", 2, 1, ["wood"]),
        ]
    ]
    times = [d(0), d(7), d(14)]
    assert set(
        s.class_starts_intersecting_time_and_area(tc.t, tc.a, times, classes)
    ) == set(tc.want)


def test_solve_simple():
    """An instructor can schedule a class at a time"""
    c = s.Class(
        1, "Embroidery", days=1, hours=1, areas=["textiles"], exclusions=[], score=0.7
    )
    got, score = s.solve(
        classes=[c],
        instructors=[s.Instructor("A", {c.class_id: [d(0)]})],
    )
    assert got == {"A": [[1, "Embroidery", d(0).isoformat()]]}
    assert score == 0.7


def test_solve_complex():
    """Run an example set of classes and instructors through the solver; assert no exceptions"""
    classes = [
        s.Class(*v)
        for v in [
            (1, "Embroidery", 1, 1, ["textiles"], [], 0.7),
            (2, "Sewing Basics", 2, 1, ["textiles"], [], 0.6),
            (3, "Basic Woodshop", 2, 1, ["wood"], [], 0.5),
            (4, "Millwork", 1, 1, ["wood"], [], 0.7),
            (5, "Basic Metals", 2, 1, ["metal"], [], 0.8),
            (6, "Metal Workshop", 1, 1, ["metal"], [], 0.4),
        ]
    ]

    people = [
        s.Instructor(*v)
        for v in [
            (
                "A",
                {
                    classes[c].class_id: [d(i) for i in [1, 7, 14, 21, 29]]
                    for c in (0, 1)
                },
            ),
            (
                "B",
                {
                    classes[c].class_id: [
                        d(i) for i in [1, 4, 5, 8, 11, 14, 22, 25, 29]
                    ]
                    for c in (2, 0, 3)
                },
            ),
            (
                "C",
                {classes[c].class_id: [d(i) for i in [5, 7, 2, 1]] for c in (4, 5, 0)},
            ),
            ("D", {classes[c].class_id: [d(i) for i in range(30)] for c in (3, 1)}),
        ]
    ]

    got, score = s.solve(classes, people)
    assert score > 0
    assert len(got) > 0


def test_solve_no_concurrent_overlap():
    """Verify classes do not overlap the same area at the same time
    when scheduled concurrently. Higher score classes win."""
    got, score = s.solve(
        classes=[
            s.Class(1, "Embroidery", 1, 1, ["textiles"], [], 0.7),
            s.Class(2, "Embroidery but cooler", 1, 1, ["textiles"], [], 0.8),
        ],
        instructors=[
            s.Instructor("A", {1: [d(0)]}),
            s.Instructor("B", {2: [d(0)]}),
        ],
    )
    assert got == {"B": [[2, "Embroidery but cooler", d(0).isoformat()]]}
    assert score == 0.8


def test_solve_no_double_booking():
    """An instructor should only be scheduled one class at a given time.
    Higher score classes should be preferred"""
    got, score = s.solve(
        classes=[
            s.Class(1, "Embroidery", 1, 1, ["textiles"], [], 0.7),
            s.Class(2, "Lasers", 1, 1, ["lasers"], [], 0.8),
        ],
        instructors=[
            s.Instructor("A", {1: [d(0)], 2: [d(0)]}),
        ],
    )
    assert got == {"A": [[2, "Lasers", d(0).isoformat()]]}
    assert score == 0.8


def test_solve_at_most_once():
    """Classes run at most once per run of the solver"""
    got, score = s.solve(
        classes=[
            s.Class(1, "Embroidery", 1, 1, ["textiles"], [], 0.7),
        ],
        instructors=[
            s.Instructor("A", {1: [d(0)]}),
            s.Instructor("B", {1: [d(1)]}),
        ],
    )
    assert got == {"A": [[1, "Embroidery", d(0).isoformat()]]}
    assert score == 0.7
