""" Methods for scheduling new classes """
import datetime
import logging
from collections import defaultdict

import pytz
from dateutil import parser as dateparser

from protohaven_api.class_automation.solver import Class, Instructor, solve
from protohaven_api.integrations import airtable
from protohaven_api.integrations.schedule import fetch_instructor_schedules

log = logging.getLogger("class_automation.scheduler")
tz = pytz.timezone("EST")


def fetch_formatted_schedule(time_min, time_max):
    """Fetch schedule info from google calendar and massage it a bit"""

    sched = fetch_instructor_schedules(time_min, time_max)
    log.info(f"Found {len(sched)} instructor schedule events from calendar")
    sched_formatted = defaultdict(list)
    for k, v in sched.items():
        k = k.strip()
        sched_formatted[k] += v
    return sched_formatted


def slice_date_range(start_date, end_date):
    """Convert all time between two datetime values into a set of
    discrete datetimes marking the potential onset of a class"""
    day_class_hours = [10, 13, 14, 18]
    class_duration = datetime.timedelta(hours=3)
    ret = []
    base_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range((end_date - start_date).days + 1):
        for j in day_class_hours:
            candidate = base_date + datetime.timedelta(days=i, hours=j)
            candidate = candidate.replace(tzinfo=tz)
            if candidate >= start_date and candidate + class_duration <= end_date:
                ret.append(candidate)
    return ret


def compute_score(cls):  # pylint: disable=unused-argument
    """Compute an integer score based on a class' desirability to run"""
    return 1.0  # Improve this later


def generate_env(
    start_date, end_date, instructor_filter=None
):  # pylint: disable=too-many-locals
    """Generates the environment to be passed to the solver"""
    instructor_caps = airtable.fetch_instructor_teachable_classes()
    sched_formatted = fetch_formatted_schedule(start_date, end_date)
    max_loads = airtable.fetch_instructor_max_load()
    instructors = []
    skipped = 0
    for k, v in sched_formatted.items():
        if len(instructor_caps[k]) == 0:
            log.warning(
                f"Instructor {k} has no capabilities listed in Airtable and will be skipped"
            )
            skipped += 1
            continue

        avail = []
        for a, b in v:
            a = dateparser.parse(a).replace(tzinfo=tz)
            b = dateparser.parse(b).replace(tzinfo=tz)
            avail += slice_date_range(a, b)

        instructors.append(
            Instructor(name=k, caps=instructor_caps[k], load=max_loads[k], avail=avail)
        )

    if skipped > 0:
        log.warning(
            f"Direct the {skipped} instructor(s) missing capabilities "
            "to this form to submit them: https://airtable.com/applultHGJxHNg69H/shr5VVjEbKd0a1DIa"
        )

    # Load classes from airtable
    classes = []
    for c in airtable.get_all_class_templates():
        if c["fields"].get("Schedulable") is True:
            classes.append(
                Class(
                    c["id"],
                    c["fields"]["Name"],
                    c["fields"]["Frequency"],
                    c["fields"]["Area"],
                    compute_score(c),
                )
            )

    log.info(
        f"Loaded {len(instructors)} instructors and {len(classes)} schedulable classes"
    )

    if instructor_filter is not None:
        instructors_filtered = [i for i in instructors if i.name in instructor_filter]
        log.info(
            f"Filtered to {len(instructors_filtered)} instructor(s): {instructors_filtered}"
        )
    else:
        instructors_filtered = instructors

    # Regardless of capabilities, the class must also be set as schedulable
    class_ids = {c.airtable_id for c in classes}
    for i in instructors_filtered:
        i.caps = [c for c in i.caps if c in class_ids]

    return {
        "classes": [c.as_dict() for c in classes],
        "instructors": [i.as_dict() for i in instructors_filtered],
    }


def solve_with_env(env):
    """Solves a scheduling problem given a specific env"""
    classes = [Class(**c) for c in env["classes"]]
    instructors = [Instructor(**i) for i in env["instructors"]]
    return solve(classes, instructors)
