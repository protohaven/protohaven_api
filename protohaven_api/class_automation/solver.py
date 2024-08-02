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
        self, airtable_id, name, hours, areas, exclusions, score
    ):  # pylint: disable=too-many-arguments
        self.airtable_id = airtable_id
        self.name = name
        self.hours = hours

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
            f"{self.name} ({self.airtable_id}, exclusions {self.exclusions}, "
            f"{self.hours}h, "
            f"{self.areas}, score={self.score})"
        )

    def as_dict(self):
        """Return class as a dict"""
        return {
            "airtable_id": self.airtable_id,
            "name": self.name,
            "hours": self.hours,
            "areas": self.areas,
            "exclusions": self.exclusions,
            "score": self.score,
        }


class Instructor:
    """Represents an instructor able to teach classes at particular times"""

    def __init__(self, name, caps, avail):
        self.name = name
        self.caps = list(set(caps))  # references Class.airtable_id; discard duplicates

        # Optionally parse str to python datetime
        self.avail = (
            [dateparser.parse(a) for a in avail]
            if len(avail) > 0 and isinstance(avail[0], str)
            else avail
        )

    def __repr__(self):
        return f"{self.name} (caps={len(self.caps)}, times={len(self.avail)}"

    def as_dict(self):
        """Return instructor as a dict"""
        return {
            "name": self.name,
            "caps": self.caps,
            "avail": self.avail,
        }


def date_range_overlaps(a0, a1, b0, b1):
    """Return True if [a0,a1] and [b0,b1] overlap"""
    if b0 <= a0 < b1:
        return True
    if b0 < a1 <= b1:
        return True
    if a0 <= b0 and a1 >= b1:
        return True
    return False


def has_area_conflict(area_occupancy, t_start, t_end):
    """Return name of class if any of `area_occupancy` lie
    within `t_start` and `t_end`, false otherwise"""
    for a_start, a_end, name in area_occupancy:
        if date_range_overlaps(a_start, a_end, t_start, t_end):
            return name
    return False


def date_within_exclusions(d, exclusions):
    """Returns the matching exclusion date if `d` is
    within any of the tuples in the list of `exclusions`"""
    for e1, e2, esched in exclusions:
        if e1 <= d <= e2:
            return esched
    return False


def solve(
    classes, instructors, area_occupancy
):  # pylint: disable=too-many-locals,too-many-branches
    """Solve a scheduling problem given a set of classes and instructors"""
    class_by_id = {cls.airtable_id: cls for cls in classes}
    areas = {a for c in classes for a in c.areas}

    # Create a dictionary of the cartesian product of classes, instructors, and times.
    # The dict values are either 0 (not assigned) or 1 (assigned)
    # Note the implicit constraint: no instructor is assigned a class they can't
    # teach, or a time they're unable to teach.
    possible_assignments = []
    skip_counters = defaultdict(lambda: defaultdict(list))
    assignment_counters = defaultdict(int)
    for instructor in instructors:
        for t in instructor.avail:
            for airtable_id in instructor.caps:
                # Skip this particular time if it's in an exclusion region
                cbid = class_by_id[airtable_id]
                excluding_class_date = date_within_exclusions(t, cbid.exclusions)
                if excluding_class_date:
                    skip_counters[instructor.name.lower()][
                        "Too soon before/after same class"
                    ].append((t, excluding_class_date, cbid.name))
                    continue

                # Skip if area already occupied
                conflict = False
                for a in cbid.areas:
                    conflict = has_area_conflict(
                        area_occupancy.get(a, []),
                        t,
                        t + datetime.timedelta(hours=cbid.hours),
                    )
                    if conflict:
                        break
                if conflict:
                    skip_counters[instructor.name.lower()][
                        "Area already occupied by other class"
                    ].append((t, t, conflict))
                    continue

                possible_assignments.append((airtable_id, instructor.name, t))
                assignment_counters[f"{instructor.name} {airtable_id}"] += 1
    log.info(f"Constructed {len(possible_assignments)} possible assignments")
    for k, v in assignment_counters.items():
        log.info(f"  {k}: {v} possible assignments")
    log.info(f"Skipped {dict(skip_counters)}")

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
                class_by_id[airtable_id].score * x[(airtable_id, instructor.name, t)]
                for instructor in instructors
                for airtable_id in instructor.caps
                for t in instructor.avail
                if x.get((airtable_id, instructor.name, t)) is not None
            ]
        ),
        "MaxScore",
    )

    # ==== Constraints ====
    # Classes do not overlap the same area at the same time
    class_areas = {c.airtable_id: c.areas for c in classes}
    times = set()
    for i in instructors:
        times.update(i.avail)
    for a in areas:
        for t in times:
            area_assigned_times = pulp.lpSum(
                [
                    [x[airtable_id, instructor.name, t]]
                    for instructor in instructors
                    for airtable_id in instructor.caps
                    if t in instructor.avail
                    and a in class_areas[airtable_id]
                    and x.get((airtable_id, instructor.name, t)) is not None
                ]
            )
            prob += area_assigned_times <= 1, f"NoOverlapRequirement_{a}_{t}"

    # Classes run at most once
    for cls in classes:
        class_assigned_count = pulp.lpSum(
            [
                x[(cls.airtable_id, instructor.name, t)]
                for instructor in instructors
                for t in instructor.avail
                if cls.airtable_id in instructor.caps
                and x.get((cls.airtable_id, instructor.name, t)) is not None
            ]
        )
        prob += (
            class_assigned_count <= 1
        ), f"NoDuplicatesRequirement_{cls.airtable_id}"

    # Instructors teach at most 1 class at any given time
    for p in instructors:
        for t in p.avail:
            booking_count = pulp.lpSum(
                [
                    x[(cls.airtable_id, p.name, t)]
                    for cls in classes
                    if cls.airtable_id in p.caps
                    and x.get((cls.airtable_id, p.name, t)) is not None
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
        class_by_id[airtable_id].score
        for instructor in instructors
        for airtable_id in instructor.caps
        for t in instructor.avail
        if x.get((airtable_id, instructor.name, t)) is not None
        and x[(airtable_id, instructor.name, t)].value() == 1
    )

    for instructor in instructors:
        for airtable_id in instructor.caps:
            for t in instructor.avail:
                if x.get((airtable_id, instructor.name, t)) is None:
                    continue
                if x[(airtable_id, instructor.name, t)].value() == 1:
                    instructor_classes[instructor.name].append(
                        [airtable_id, class_by_id[airtable_id].name, t.isoformat()]
                    )
    log.info(f"Scheduler result: {instructor_classes}, final score {final_score}")
    return (
        dict(instructor_classes),
        final_score,
        {k: dict(v) for k, v in skip_counters.items()},
    )
