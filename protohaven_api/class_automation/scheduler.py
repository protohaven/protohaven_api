""" Methods for scheduling new classes """
import datetime
import logging
from collections import defaultdict

import holidays
import pytz
from dateutil import parser as dateparser

from protohaven_api.class_automation.solver import (
    Class,
    Instructor,
    date_range_overlaps,
    solve,
)
from protohaven_api.integrations import airtable
from protohaven_api.integrations.schedule import fetch_instructor_schedules

log = logging.getLogger("class_automation.scheduler")
tz = pytz.timezone("EST")


def fetch_formatted_schedule(time_min, time_max):
    """Fetch schedule info from google calendar and massage it a bit"""

    sched = fetch_instructor_schedules(
        time_min.replace(tzinfo=None), time_max.replace(tzinfo=None)
    )
    log.info(f"Found {len(sched)} instructor schedule events from calendar")
    sched_formatted = defaultdict(list)
    for k, v in sched.items():
        k = k.strip().lower()
        sched_formatted[k] += v
    return sched_formatted


def slice_date_range(start_date, end_date):
    """Convert all time between two datetime values into a set of
    discrete datetimes marking the potential onset of a class"""
    day_class_hours = [10, 13, 14, 18]
    evening_threshold = 17
    evening_only_days = {0, 1, 2, 3, 4}  # Monday is 0, Sunday is 6
    class_duration = datetime.timedelta(hours=3)
    ret = []
    base_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range((end_date - start_date).days + 1):
        for j in day_class_hours:
            candidate = base_date + datetime.timedelta(days=i, hours=j)
            if candidate.weekday() in evening_only_days and j < evening_threshold:
                continue  # Some days, we only allow classes to run in the evening
            candidate = candidate.replace(tzinfo=tz)
            if candidate >= start_date and candidate + class_duration <= end_date:
                ret.append(candidate)
    return ret


def compute_score(cls):  # pylint: disable=unused-argument
    """Compute an integer score based on a class' desirability to run"""
    return 1.0  # Improve this later


def generate_env(
    start_date, end_date, instructor_filter=None, exclude_holidays=True
):  # pylint: disable=too-many-locals
    """Generates the environment to be passed to the solver"""

    if instructor_filter is not None:
        instructor_filter = [k.lower() for k in instructor_filter]
        log.info(f"Filter: {instructor_filter}")
    instructor_caps = airtable.fetch_instructor_teachable_classes()
    sched_formatted = fetch_formatted_schedule(start_date, end_date)
    max_loads = airtable.fetch_instructor_max_load()
    cur_sched = [
        c
        for c in airtable.get_class_automation_schedule()
        if c["fields"].get("Neon ID") is not None
    ]
    instructors = []
    skipped = 0
    if exclude_holidays:
        log.info("Instructor availability that falls on US holidays will be ignored")
    else:
        log.warn(
            "Instructor availability that falls on US holidays will NOT be ignored"
        )

    for k, v in sched_formatted.items():
        k = k.lower()
        log.info(f"Handling {k}")
        if len(instructor_caps[k]) == 0:
            log.warning(
                f"Instructor {k} has no capabilities listed in Airtable and will be skipped (schedule: {v})"
            )
            skipped += 1
            continue

        if instructor_filter is not None and k not in instructor_filter:
            log.info(f"Skipping instructor {k} (not in filter)")
            continue

        avail = []
        for a, b in v:
            a = dateparser.parse(a).replace(tzinfo=tz)
            b = dateparser.parse(b).replace(tzinfo=tz)
            avail += slice_date_range(a, b)

        if exclude_holidays:
            us_holidays = holidays.US()
            avail = [a for a in avail if a not in us_holidays]

        instructors.append(
            Instructor(name=k, caps=instructor_caps[k], load=max_loads[k], avail=avail)
        )

    if skipped > 0:
        log.warning(
            f"Direct the {skipped} instructor(s) missing capabilities "
            "to this form to submit them: https://airtable.com/applultHGJxHNg69H/shr5VVjEbKd0a1DIa"
        )

    # Filter out any classes that have/will run too recently
    last_run = defaultdict(
        lambda: datetime.datetime(year=2001, month=1, day=1).astimezone(tz)
    )
    area_occupancy = defaultdict(list)
    for c in cur_sched:
        t = dateparser.parse(c["fields"]["Start Time"]).astimezone(tz)
        last_run[c["fields"]["Class"][0]] = max(last_run[c["id"]], t)
        for i in range(c["fields"]["Days (from Class)"][0]):
            ao = [
                t + datetime.timedelta(days=7 * i),
                t
                + datetime.timedelta(
                    days=7 * i, hours=c["fields"]["Hours (from Class)"][0]
                ),
            ]
            if date_range_overlaps(ao[0], ao[1], start_date, end_date):
                area_occupancy[c["fields"]["Area (from Class)"][0]].append(ao)
    for v in area_occupancy.values():
        v.sort(key=lambda o: o[1])
    log.info(f"Computed last runtime of {len(last_run)} different classes")
    log.info(f"Computed occupancy of {len(area_occupancy)} different areas")

    # Load classes from airtable
    classes = []
    for c in airtable.get_all_class_templates():
        if c["fields"].get("Schedulable") is True:
            classes.append(
                Class(
                    c["id"],
                    c["fields"]["Name"],
                    c["fields"]["Period"],
                    c["fields"]["Hours"],
                    c["fields"]["Area"],
                    last_run[c["id"]],
                    compute_score(c),
                )
            )

    log.info(
        f"Loaded {len(instructors)} instructors and {len(classes)} schedulable classes"
    )
    unavailable = set(instructor_caps.keys()) - {i.name for i in instructors}
    if len(unavailable) > 0:
        log.warning(
            f"{len(unavailable)} instructor(s) with caps are not present in the final list: {unavailable}"
        )

    # Regardless of capabilities, the class must also be set as schedulable
    class_ids = {c.airtable_id for c in classes}
    for i in instructors:
        i.caps = [c for c in i.caps if c in class_ids]

    return {
        "classes": [c.as_dict() for c in classes],
        "instructors": [i.as_dict() for i in instructors],
        "area_occupancy": dict(
            area_occupancy.items()
        ),  # Convert defaultdict to dict for yaml serialization
    }


def solve_with_env(env):
    """Solves a scheduling problem given a specific env"""
    classes = [Class(**c) for c in env["classes"]]
    instructors = [Instructor(**i) for i in env["instructors"]]
    return solve(classes, instructors, env["area_occupancy"])


def format_class(cls):
    """Convert a class into bulleted representation, for email summary"""
    _, name, date = cls
    start = dateparser.parse(date).astimezone(pytz.timezone("EST"))
    return f"- {start.strftime('%A %b %-d, %-I%p')}: {name}"


def push_schedule(sched):
    """Pushes the created schedule to airtable and generates notifications"""
    email_map = {k.lower(): v for k, v in airtable.get_instructor_email_map().items()}
    payload = []
    for inst, classes in sched.items():
        for record_id, _, date in classes:
            payload.append(
                {
                    "Instructor": inst,
                    "Email": email_map[inst],
                    "Start Time": date,
                    "Class": [record_id],
                }
            )

    notifications = []
    for inst, classes in sched.items():
        classes.sort(key=lambda c: c[2])
        formatted = [format_class(f) for f in classes]
        subject = "Confirm class schedule"
        email = email_map[inst]
        body = f"Hello, {inst.title()}!"
        body += "\nWe have a new set of potential classes for you to teach, and we are"
        body += " looking for your confirmation:\n\n"
        body += "\n".join(formatted)
        body += "\n\nConfirm the classes you would like to teach ASAP by going to"
        body += " http://api.protohaven.org/instructor/class."
        body += "\n\nPlease note:"
        body += "\n - Some classes may overlap in time; just pick whichever you prefer"
        body += "\n - Not all classes you confirm will be scheduled"
        body += "\n - Not all classes that are scheduled will fill up."
        body += "\n\nWe will schedule your confirmed classes in the next few days."
        body += "\n\nThank you!"
        notifications.append(
            {"id": None, "subject": subject, "body": body, "target": email}
        )

    for p in payload:
        airtable.append_classes_to_schedule([p])
    return notifications
