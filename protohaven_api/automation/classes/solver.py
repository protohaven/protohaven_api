"""Solves class scheduling problems given an environment containing Classes and Instructors"""
# https://stackoverflow.com/questions/42450533/bin-packing-python-query-with-variable-people-cost-and-sizes
# https://gist.github.com/sameerkumar18/086cc6bdc277dc1cefb4374fa7b0327a
import datetime
import logging
from collections import defaultdict

from dateutil import parser as dateparser
from pulp import constants as pulp_constants
from pulp import pulp

from protohaven_api.automation.classes.validation import date_range_overlaps

log = logging.getLogger("class_automation.solver")


class Class:
    """Represents a class template schedulable, in one or more areas, with score"""

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, class_id, name, hours, days, areas, exclusions, score
    ):
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

    def expand(self, start_time):
        """Generate a list of time intervals based on a given `start_time` for
        which the class would be active"""
        for d in range(self.days):
            t0 = start_time + datetime.timedelta(days=7 * d)
            t1 = t0 + datetime.timedelta(hours=self.hours)
            yield (t0, t1)

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
            "days": self.days,
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


def _find_overlap(c1, t1, c2, t2):
    """Expand two classes starting at two times and return
    True if they overlap
    """
    for c1t0, c1t1 in c1.expand(t1):
        for c2t0, c2t1 in c2.expand(t2):
            if date_range_overlaps(c1t0, c1t1, c2t0, c2t1):
                return True
    return False


def get_overlapping(c1, t1, classes, times):
    """Yields a sequence of (class_id, start_time) of classes that would
    conflict with class `c` running at time `t`.
    Note that duplicate values may be returned."""
    for c2 in classes:
        # Classes without intersecting areas don't have a chance of overlapping
        if len(set(c1.areas).intersection(set(c2.areas))) == 0:
            continue
        for t2 in times:
            if _find_overlap(c1, t1, c2, t2):
                yield c2.class_id, t2


def _time_weight(t, earliest, latest):
    """Penalize later classes"""
    if latest == earliest:
        return 0
    return -0.001 * (
        (t - earliest).total_seconds() / (latest - earliest).total_seconds()
    )


def solve(classes, instructors):  # pylint: disable=too-many-locals,too-many-branches
    """Solve a scheduling problem given a set of classes and instructors"""
    class_by_id = {cls.class_id: cls for cls in classes}

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
    times = {a for i in instructors for a in i.avail}
    earliest = min(times)
    latest = max(times)

    # Objective: maximize the total score of classes assigned
    prob += (
        pulp.lpSum(
            [
                (class_by_id[class_id].score + _time_weight(t, earliest, latest))
                * x[(class_id, instructor.name, t)]
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
    for i in instructors:
        for class_id in i.caps:
            c = class_by_id.get(class_id)
            for t in i.avail:
                overlaps = set(get_overlapping(c, t, class_by_id.values(), times))
                # Include all instructors that could teach each
                # overlap at the computed start time
                area_assigned_times = pulp.lpSum(
                    [
                        x[(cid, i2.name, start)]
                        for cid, start in overlaps
                        for i2 in instructors
                        if start in i2.avail
                        and cid in i2.caps
                        and x.get((cid, i2.name, start)) is not None
                    ]
                )
                prob += (
                    area_assigned_times <= 1,
                    f"NoOverlapRequirement_{i.name}_{class_id}_{t}",
                )

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
