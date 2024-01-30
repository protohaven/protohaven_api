# https://stackoverflow.com/questions/42450533/bin-packing-python-query-with-variable-people-cost-and-sizes
# https://gist.github.com/sameerkumar18/086cc6bdc277dc1cefb4374fa7b0327a

import logging
from collections import defaultdict, namedtuple
from enum import Enum

from pulp import constants as pulp_constants
from pulp import pulp

log = logging.getLogger("class_automation.solver")


class Class:
    def __init__(self, airtable_id, name, freq, area, score):
        self.airtable_id = airtable_id
        self.name = name
        self.freq = freq
        self.area = area
        # Score is a normalized expected value based on revenue, likelihood to fill,
        # cost of materials etc.
        self.score = score

    def __repr__(self):
        return f"{self.name} ({self.airtable_id}, max {self.freq}/mo, {self.area}, score={self.score})"

    def as_dict(self):
        return {
            "airtable_id": self.airtable_id,
            "name": self.name,
            "freq": self.freq,
            "area": self.area,
            "score": self.score,
        }


class Instructor:
    def __init__(self, name, caps, load, avail):
        self.name = name
        self.caps = caps  # references Class.airtable_id
        self.load = load  # classes teachable per month
        self.avail = avail

    def __repr__(self):
        return f"{self.name} (caps={len(self.caps)}, times={len(self.avail)}, load={self.load})"

    def as_dict(self):
        return {
            "name": self.name,
            "caps": self.caps,
            "load": self.load,
            "avail": self.avail,
        }


def solve(classes, instructors):
    class_by_id = {cls.airtable_id: cls for cls in classes}
    areas = {c.area for c in classes}
    instructors_by_name = {p.name: p for p in instructors}

    # Create a dictionary of the cartesian product of classes, instructors, and times.
    # The dict values are either 0 (not assigned) or 1 (assigned)
    # Note the implicit constraint: no instructor is assigned a class they can't
    # teach, or a time they're unable to teach.
    possible_assignments = [
        (cls, instructor.name, t)
        for instructor in instructors
        for t in instructor.avail
        for cls in instructor.caps
    ]
    log.info(f"Constructed {len(possible_assignments)} possible assignments")
    x = pulp.LpVariable.dicts(
        "ClassAssignedToInstructorAtTime",
        possible_assignments,
        lowBound=0,
        upBound=1,
        cat=pulp_constants.LpInteger,
    )

    # Model formulation
    prob = pulp.LpProblem("Class_Packing_Problem", pulp_constants.LpMaximize)

    # Objective: maximize the total score of classes assigned
    prob += pulp.lpSum(
        [
            class_by_id[cls].score * x[(cls, instructor.name, t)]
            for instructor in instructors
            for cls in instructor.caps
            for t in instructor.avail
        ]
    )

    # ==== Constraints ====

    # Classes do not overlap the same area at the same time
    class_areas = {c.airtable_id: c.area for c in classes}
    for a in areas:
        areaAssignedTimes = pulp.lpSum(
            [x[cls, instructor.name, t]]
            for instructor in instructors
            for t in instructor.avail
            for cls in instructor.caps
            if class_areas[cls] == a
        )
        prob += areaAssignedTimes <= 1

    # Classes run at most their `freq` value
    for cls in classes:
        clsAssignedCount = pulp.lpSum(
            [
                x[(cls.airtable_id, instructor.name, t)]
                for instructor in instructors
                for t in instructor.avail
                if cls.airtable_id in instructor.caps
            ]
        )
        prob += clsAssignedCount <= cls.freq

    # Each class-time is assigned to at most 1 instructor
    time_map = defaultdict(set)
    for p in instructors:
        for t in p.avail:
            time_map[t].add(p.name)
    for cls in classes:
        for t, names in time_map.items():
            clsTimeAssignedCount = pulp.lpSum(
                [
                    x[(cls.airtable_id, p, t)]
                    for p in names
                    if cls in instructors_by_name[p].caps
                ]
            )
            prob += clsTimeAssignedCount <= 1

    # No instructor is filled beyond their desired class rate
    for instructor in instructors:
        assignedLoad = pulp.lpSum(
            [
                x[(cls, instructor.name, t)]
                for cls in instructor.caps
                for t in instructor.avail
            ]
        )
        prob += assignedLoad <= instructor.load

        # For instructors with reasonable availability and capabilities, they must have at least one class scheduled
        if len(instructor.avail) >= 3 and len(instructor.caps) != 0:
            prob += assignedLoad >= 1.0
        else:
            log.warning(
                f"Instructor {instructor.name} has only {len(instructor.avail)} available times and {len(instructor.caps)} classes to teach - they may not be scheduled"
            )

    # ==== Run the solver and compute stats ====
    prob.solve()
    instructor_classes = defaultdict(list)
    final_score = sum(
        [
            class_by_id[cls].score
            for instructor in instructors
            for cls in instructor.caps
            for t in instructor.avail
            if x[(cls, instructor.name, t)].value() == 1
        ]
    )

    for instructor in instructors:
        for cls in instructor.caps:
            for t in instructor.avail:
                if x[(cls, instructor.name, t)].value() == 1:
                    instructor_classes[instructor.name].append(
                        [cls, class_by_id[cls].name, t.isoformat()]
                    )
    return (dict(instructor_classes), final_score)
