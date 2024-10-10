"""Solves class scheduling problems given an environment containing Classes and Instructors"""
# https://stackoverflow.com/questions/42450533/bin-packing-python-query-with-variable-people-cost-and-sizes
# https://gist.github.com/sameerkumar18/086cc6bdc277dc1cefb4374fa7b0327a
import datetime
import logging
from collections import defaultdict

from dateutil import parser as dateparser
from pulp import constants as pulp_constants
from pulp import pulp

log = logging.getLogger("class_automation.solver")


class Class:
    """Represents a class template schedulable, in one or more areas, with score"""

    def __init__(
        self, class_id, name, hours, days, areas, exclusions, score
    ):  # pylint: disable=too-many-arguments
        self.class_id = class_id  # The ID in airtable
        self.name = name
        self.hours = hours
        self.days = days

        assert isinstance(areas, list)
        self.areas = areas

        if len(exclusions) > 0 and isinstance(exclusions[0][0], str):
            # Convert from string to Date if required
            self.exclusions = [[dateparser.parse(e) for e in ee] for ee in exclusions]
        else:
            self.exclusions = exclusions
        # Score is a normalized expected value based on revenue, likelihood to fill,
        # cost of materials etc.
        self.score = score

    def __repr__(self):
        return (
            f"{self.name} ({self.class_id}, exclusions {self.exclusions}, "
            f"{self.hours}h, "
            f"{self.areas}, score={self.score})"
        )

    def as_dict(self):
        """Return class as a dict"""
        return {
            "class_id": self.class_id,
            "name": self.name,
            "hours": self.hours,
            "areas": self.areas,
            "exclusions": self.exclusions,
            "score": self.score,
        }


class Instructor:
    """Represents an instructor able to teach classes at particular times"""

    def __init__(self, name, candidates, rejected=None):
        """Candidates is a dict of {Class.class_id: [(t0, t1), ...]}"""
        self.name = name
        # references Class.class_id; discard duplicates.
        # We use List instead of Set so we can serialize JSON
        self.caps = list(set(candidates.keys()))
        self.avail = list(
            {
                (dateparser.parse(a) if isinstance(a, str) else a)
                for cap, avail in candidates.items()
                for a in avail
            }
        )
        self.candidates = {
            cap: [dateparser.parse(a) if isinstance(a, str) else a for a in aa]
            for cap, aa in candidates.items()
        }
        self.rejected = rejected or {}

    def __repr__(self):
        return f"{self.name} (caps={len(self.caps)}, times={len(self.avail)}"

    def as_dict(self):
        """Return instructor as a dict"""
        return {
            "name": self.name,
            "candidates": self.candidates,
            "rejected": self.rejected,
        }


def class_starts_intersecting_time_and_area(t, a, times, classes):
    """Yields a sequence of (class_id, time) of classes that use area `a` and
    which would overlap at time `t`"""
    for tt in times:
        for c in classes:
            if a not in c.areas:
                continue
            for session in range(c.days):
                start = tt + datetime.timedelta(days=7 * session)
                end = start + datetime.timedelta(hours=c.hours)
                if start <= t <= end:
                    yield c.class_id, tt
                    break


def solve(classes, instructors):  # pylint: disable=too-many-locals,too-many-branches
    """Solve a scheduling problem given a set of classes and instructors"""
    class_by_id = {cls.class_id: cls for cls in classes}
    areas = {a for c in classes for a in c.areas}

    # Create a dictionary of the cartesian product of classes, instructors, and times.
    # The dict values are either 0 (not assigned) or 1 (assigned)
    # Note the implicit constraint: no instructor is assigned a class they can't
    # teach, or a time they're unable to teach.
    possible_assignments = []
    for instructor in instructors:
        for class_id, tt in instructor.candidates.items():
            for t in tt:
                possible_assignments.append((class_id, instructor.name, t))
    log.info(f"Constructed {len(possible_assignments)} possible assignments")

    x = pulp.LpVariable.dicts(
        "ClassAssignedToInstructorAtTime",
        possible_assignments,
        cat="Binary",
    )

    # Model formulation
    prob = pulp.LpProblem("Class_Packing_Problem", pulp_constants.LpMaximize)

    # Objective: maximize the total score of classes assigned
    prob += (
        pulp.lpSum(
            [
                class_by_id[class_id].score * x[(class_id, instructor.name, t)]
                for instructor in instructors
                for class_id in instructor.caps
                for t in instructor.avail
                if x.get((class_id, instructor.name, t)) is not None
            ]
        ),
        "MaxScore",
    )

    # ==== Constraints ====
    # Classes do not overlap the same area at the same time
    times = set()
    for i in instructors:
        times.update(i.avail)
    for a in areas:
        for t in times:
            # As classes may run for multiple days, we must first
            # pick out a set of candidate classes which would overlap time `t`
            # and area `a`, then collect instructors who would potentially
            # be teaching that class at that time.
            class_starts = list(
                class_starts_intersecting_time_and_area(
                    t, a, times, class_by_id.values()
                )
            )
            area_assigned_times = pulp.lpSum(
                [
                    x[(class_id, instructor.name, start)]
                    for class_id, start in class_starts
                    for instructor in instructors
                    if start in instructor.avail
                    and class_id in instructor.caps
                    and x.get((class_id, instructor.name, start)) is not None
                ]
            )
            prob += area_assigned_times <= 1, f"NoOverlapRequirement_{a}_{t}"

    # Classes run at most once
    for cls in classes:
        class_assigned_count = pulp.lpSum(
            [
                x[(cls.class_id, instructor.name, t)]
                for instructor in instructors
                for t in instructor.avail
                if cls.class_id in instructor.caps
                and x.get((cls.class_id, instructor.name, t)) is not None
            ]
        )
        prob += (class_assigned_count <= 1), f"NoDuplicatesRequirement_{cls.class_id}"

    # Instructors teach at most 1 class at any given time
    for p in instructors:
        for t in p.avail:
            booking_count = pulp.lpSum(
                [
                    x[(cls.class_id, p.name, t)]
                    for cls in classes
                    if cls.class_id in p.caps
                    and x.get((cls.class_id, p.name, t)) is not None
                ]
            )
            prob += (
                booking_count <= 1,
                f"NoDoubleBookedInstructorRequirement_{p.name}_{t}",
            )

    # ==== Run the solver and compute stats ====
    prob.solve()
    instructor_classes = defaultdict(list)
    final_score = sum(
        class_by_id[class_id].score
        for instructor in instructors
        for class_id in instructor.caps
        for t in instructor.avail
        if x.get((class_id, instructor.name, t)) is not None
        and x[(class_id, instructor.name, t)].value() == 1
    )

    for instructor in instructors:
        for class_id in instructor.caps:
            for t in instructor.avail:
                if x.get((class_id, instructor.name, t)) is None:
                    continue
                if x[(class_id, instructor.name, t)].value() == 1:
                    instructor_classes[instructor.name].append(
                        [class_id, class_by_id[class_id].name, t.isoformat()]
                    )
    log.info(f"Scheduler result: {instructor_classes}, final score {final_score}")
    return (dict(instructor_classes), final_score)
