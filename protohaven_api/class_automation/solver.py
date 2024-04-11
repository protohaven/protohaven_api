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
    """Represents a class template schedulable at a period, in an area, with score"""

    def __init__(
        self, airtable_id, name, period, hours, area, last_run, score
    ):  # pylint: disable=too-many-arguments
        self.airtable_id = airtable_id
        self.name = name
        self.period = period
        self.hours = hours
        self.area = area
        self.last_run = (
            dateparser.parse(last_run) if isinstance(last_run, str) else last_run
        )
        # Score is a normalized expected value based on revenue, likelihood to fill,
        # cost of materials etc.
        self.score = score

    def __repr__(self):
        return (
            f"{self.name} ({self.airtable_id}, last run {self.last_run} for {self.hours}, "
            f"max every {self.period} months, "
            "{self.area}, score={self.score})"
        )

    def as_dict(self):
        """Return class as a dict"""
        return {
            "airtable_id": self.airtable_id,
            "name": self.name,
            "period": self.period,
            "hours": self.hours,
            "area": self.area,
            "last_run": self.last_run,
            "score": self.score,
        }


class Instructor:
    """Represents an instructor able to teach classes at particular times"""

    def __init__(self, name, caps, load, avail):
        self.name = name
        self.caps = caps  # references Class.airtable_id
        self.load = load  # classes teachable per month
        self.avail = (
            [dateparser.parse(a) for a in avail] if isinstance(avail[0], str) else avail
        )

    def __repr__(self):
        return f"{self.name} (caps={len(self.caps)}, times={len(self.avail)}, load={self.load})"

    def as_dict(self):
        """Return instructor as a dict"""
        return {
            "name": self.name,
            "caps": self.caps,
            "load": self.load,
            "avail": self.avail,
        }


def date_range_overlaps(a0, a1, b0, b1):
    """Return True if [a0,a1] and [b0,b1] overlap"""
    if b1 > a0 > b0:
        return True
    if b1 > a1 > b0:
        return True
    if a0 < b0 and a1 > b1:
        return True
    return False


def has_area_conflict(area_occupancy, t_start, t_end):
    """Return true if any of `area_occupancy` lie within `t_start` and `t_end`, false otherwise"""
    for a_start, a_end in area_occupancy:
        if date_range_overlaps(a_start, a_end, t_start, t_end):
            return True
    return False


def solve(
    classes, instructors, area_occupancy
):  # pylint: disable=too-many-locals,too-many-branches
    """Solve a scheduling problem given a set of classes and instructors"""
    class_by_id = {cls.airtable_id: cls for cls in classes}
    areas = {a for c in classes for a in c.area}
    instructors_by_name = {p.name: p for p in instructors}

    # Create a dictionary of the cartesian product of classes, instructors, and times.
    # The dict values are either 0 (not assigned) or 1 (assigned)
    # Note the implicit constraint: no instructor is assigned a class they can't
    # teach, or a time they're unable to teach.
    possible_assignments = []
    for instructor in instructors:
        for t in instructor.avail:
            for airtable_id in instructor.caps:
                # Skip if assignment is too recent
                cbid = class_by_id[airtable_id]
                if t < cbid.last_run + datetime.timedelta(days=30 * cbid.period):
                    continue

                # Skip if area already occupied
                conflict = False
                for a in cbid.area:
                    if has_area_conflict(
                        area_occupancy.get(a, []),
                        t,
                        t + datetime.timedelta(hours=cbid.hours),
                    ):
                        conflict = True
                    break
                if conflict:
                    continue

                possible_assignments.append((airtable_id, instructor.name, t))
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
                class_by_id[airtable_id].score * x[(airtable_id, instructor.name, t)]
                for instructor in instructors
                for airtable_id in instructor.caps
                for t in instructor.avail
                if x.get((airtable_id, instructor.name, t))
                is not None  # some assignments filtered
            ]
        ),
        "MaxScore",
    )

    # ==== Constraints ====

    # Classes do not overlap the same area at the same time
    class_areas = {c.airtable_id: c.area for c in classes}
    times = set()
    for i in instructors:
        times.update(i.avail)

    for a in areas:
        for t in times:
            area_assigned_times = pulp.lpSum(
                [x[airtable_id, instructor.name, t]]
                for instructor in instructors
                for airtable_id in instructor.caps
                if t in instructor.avail
                and class_areas[airtable_id] == a
                and x.get((airtable_id, instructor.name, t)) is not None
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
        # Classes are scheduled
        # prob += class_assigned_count != 0

    # Each class-time is assigned to at most 1 instructor
    time_map = defaultdict(set)
    for p in instructors:
        for t in p.avail:
            time_map[t].add(p.name)
    for cls in classes:
        for t, names in time_map.items():
            class_time_assigned_count = pulp.lpSum(
                [
                    x[(cls.airtable_id, p, t)]
                    for p in names
                    if cls.airtable_id in instructors_by_name[p].caps
                    and x.get((cls.airtable_id, p, t)) is not None
                ]
            )
            prob += (
                class_time_assigned_count <= 1,
                f"NoDupeInstructorRequirement_{cls.airtable_id}_{t}",
            )

    # No instructor is filled beyond their desired class rate
    for instructor in instructors:
        assigned_load = pulp.lpSum(
            [
                x[(airtable_id, instructor.name, t)]
                for airtable_id in instructor.caps
                for t in instructor.avail
                if x.get((airtable_id, instructor.name, t)) is not None
            ]
        )
        prob += (
            assigned_load <= instructor.load,
            f"NoOverloadRequirement_{instructor.name}",
        )

        # Extra: at least one class is assigned to each instructor
        # prob += assigned_load != 0

        # For instructors with reasonable availability and capabilities,
        # they must have at least one class scheduled
        if len(instructor.avail) >= 3 and len(instructor.caps) != 0:
            prob += assigned_load >= 1.0, f"MinLoadrequirement_{instructor.name}"
        else:
            log.warning(
                f"Instructor {instructor.name} has only {len(instructor.avail)} available "
                f"times and {len(instructor.caps)} classes to teach - they may not be scheduled"
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
    return (dict(instructor_classes), final_score)
