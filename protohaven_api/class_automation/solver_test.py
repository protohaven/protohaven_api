"""Test behavior of linear solver for class scheduling"""
import datetime

from protohaven_api.class_automation import solver as s


def d(i, h=0):
    """Returns a date based on an integer, for testing"""
    return datetime.datetime(year=2025, month=1, day=1) + datetime.timedelta(
        days=i, hours=h
    )


OLD = d(-31)


def test_has_area_conflict():
    """Verify behavior of date math in has_area_conflict"""
    # Perfect overlap
    assert s.has_area_conflict([(d(0, 0), d(0, 3))], d(0, 0), d(0, 3)) is True
    # Slightly before
    assert s.has_area_conflict([(d(0, 1), d(0, 4))], d(0, 0), d(0, 3)) is True
    # Slightly after
    assert s.has_area_conflict([(d(0, 0), d(0, 3))], d(0, 1), d(0, 4)) is True
    # Enclosed
    assert s.has_area_conflict([(d(0, 0), d(0, 3))], d(0, 1), d(0, 2)) is True
    # Enclosing
    assert s.has_area_conflict([(d(0, 1), d(0, 2))], d(0, 0), d(0, 3)) is True
    # Directly before
    assert s.has_area_conflict([(d(0, 3), d(0, 6))], d(0, 0), d(0, 3)) is False
    # Directly after
    assert s.has_area_conflict([(d(0, 0), d(0, 3))], d(0, 3), d(0, 6)) is False
    # Different day
    assert s.has_area_conflict([(d(1, 0), d(1, 3))], d(0, 0), d(0, 3)) is False


def test_solve_simple():
    """An instructor can schedule a class at a time"""
    got, score = s.solve(
        classes=[s.Class(1, "Embroidery", 1, 3, ["textiles"], OLD, 0.7)],
        instructors=[s.Instructor("A", [1], 6, [d(0)])],
        area_occupancy={},
    )
    assert got == {"A": [[1, "Embroidery", "2025-01-01T00:00:00"]]}
    assert score == 0.7


def test_solve_complex():
    """Run an example set of classes and instructors through the solver"""
    classes = [
        s.Class(*v)
        for v in [
            (1, "Embroidery", 1, 3, ["textiles"], OLD, 0.7),
            (2, "Sewing Basics", 2, 3, ["textiles"], OLD, 0.6),
            (3, "Basic Woodshop", 2, 3, ["wood"], OLD, 0.5),
            (4, "Millwork", 1, 3, ["wood"], OLD, 0.7),
            (5, "Basic Metals", 2, 3, ["metal"], OLD, 0.8),
            (6, "Metal Workshop", 1, 3, ["metal"], OLD, 0.4),
        ]
    ]

    people = [
        s.Instructor(*v)
        for v in [
            ("A", [1, 2], 6, [d(i) for i in [1, 7, 14, 21, 29]]),
            (
                "B",
                [3, 1, 4],
                4,
                [d(i) for i in [1, 4, 5, 8, 11, 14, 22, 25, 29]],
            ),
            ("C", [5, 6, 1], 2, [d(i) for i in [5, 7, 2, 1]]),
            ("D", [4, 2], 1, [d(i) for i in range(30)]),
        ]
    ]

    area_occupancy = {}

    s.solve(classes, people, area_occupancy)
    # (schedule, load, score) = solve(classes, people)


def test_solve_no_area_overlap():
    """When an instructor attempts to schedule a class, the solver prefers
    not offering the class instead of scheduling it in an occupied area"""
    pd = (d(1), d(1, 3))
    got, score = s.solve(
        classes=[s.Class(1, "Embroidery", 1, 3, ["textiles"], OLD, 0.7)],
        instructors=[s.Instructor("A", [1], 6, [pd[0]])],
        area_occupancy={"textiles": [pd]},
    )
    assert not got
    assert score == 0


def test_solve_too_recent():
    """When an instructor attempts to schedule a class, the solver prefers not
    offering the class instead of running it too soon after a prior run"""
    pd = (d(1), d(1, 3))
    got, score = s.solve(
        classes=[s.Class(1, "Embroidery", 1, 3, ["textiles"], d(-15), 0.7)],
        instructors=[s.Instructor("A", [1], 6, [pd[0]])],
        area_occupancy={},
    )
    assert not got
    assert score == 0


def test_solve_no_concurrent_overlap():
    """Verify classes do not overlap the same area at the same time
    when scheduled concurrently. Higher score classes win."""
    got, score = s.solve(
        classes=[
            s.Class(1, "Embroidery", 1, 3, ["textiles"], OLD, 0.7),
            s.Class(2, "Embroidery but cooler", 1, 3, ["textiles"], OLD, 0.8),
        ],
        instructors=[
            s.Instructor("A", [1], 6, [d(0)]),
            s.Instructor("B", [2], 6, [d(0)]),
        ],
        area_occupancy={},
    )
    assert got == {"B": [[2, "Embroidery but cooler", "2025-01-01T00:00:00"]]}
    assert score == 0.8


def test_solve_at_most_once():
    """Classes run at most once per run of the solver"""
    got, score = s.solve(
        classes=[
            s.Class(1, "Embroidery", 1, 3, ["textiles"], OLD, 0.7),
        ],
        instructors=[
            s.Instructor("A", [1], 6, [d(0)]),
            s.Instructor("B", [1], 6, [d(1)]),
        ],
        area_occupancy={},
    )
    assert got == {"A": [[1, "Embroidery", "2025-01-01T00:00:00"]]}
    assert score == 0.7


def test_solve_instructor_load():
    """Instructors are not filled past their capacity to teach"""
    classes = [
        s.Class(1, "Embroidery", 1, 3, ["textiles"], OLD, 0.7),
        s.Class(2, "More embroidery", 1, 3, ["textiles"], OLD, 0.7),
    ]
    instructors = [
        s.Instructor("A", [1, 2], 1, [d(0), d(1)]),
    ]
    got, score = s.solve(classes, instructors, area_occupancy={})
    assert got == {"A": [[1, "Embroidery", "2025-01-01T00:00:00"]]}
    assert score == 0.7

    instructors[0].load = 2  # increasing load allows scheduling more classes
    got, score = s.solve(classes, instructors, area_occupancy={})
    assert score == 1.4
