""" Methods for scheduling new classes """
import datetime
import logging
from collections import defaultdict

import holidays
from dateutil import parser as dateparser

from protohaven_api.class_automation.solver import (
    Class,
    Instructor,
    date_range_overlaps,
    solve,
)
from protohaven_api.config import tz, tznow
from protohaven_api.integrations import airtable
from protohaven_api.integrations.schedule import fetch_instructor_schedules

log = logging.getLogger("class_automation.scheduler")


def fetch_formatted_schedule_gcal(_, time_min, time_max):
    """DEPRECATED: Fetch schedule info from google calendar and massage it a bit"""
    sched = fetch_instructor_schedules(
        time_min.replace(tzinfo=None), time_max.replace(tzinfo=None)
    )
    log.info(f"Found {len(sched)} instructor schedule events from calendar")
    sched_formatted = defaultdict(list)
    for k, v in sched.items():
        k = k.strip().lower()
        sched_formatted[k] += v
    return sched_formatted


def fetch_formatted_schedule(inst_filter, time_min, time_max):
    result = {}
    for inst in inst_filter:
        rows = airtable.get_instructor_availability(inst)
        # Have to drop the record IDs
        result[inst] = [[a[1].isoformat(), a[2].isoformat()] for a in airtable.expand_instructor_availability(rows, time_min, time_max)]
    return result


def slice_date_range(start_date, end_date):
    """Convert all time between two datetime values into a set of
    discrete datetimes marking the potential onset of a class"""
    day_class_hours = [10, 13, 14, 18]
    evening_threshold = 17
    evening_only_days = {0, 1, 2, 3, 4}  # Monday is 0, Sunday is 6
    class_duration = datetime.timedelta(hours=3)
    ret = []
    base_date = start_date.replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    for i in range((end_date - start_date).days + 1):
        for j in day_class_hours:
            candidate = base_date + datetime.timedelta(days=i, hours=j)
            if candidate.weekday() in evening_only_days and j < evening_threshold:
                continue  # Some days, we only allow classes to run in the evening
            candidate = tz.localize(candidate)
            if candidate >= start_date and candidate + class_duration <= end_date:
                ret.append(candidate)
    return ret


def compute_score(cls):  # pylint: disable=unused-argument
    """Compute an integer score based on a class' desirability to run"""
    return 1.0  # Improve this later


def build_instructor(k, v, caps, occupancy):
    """Create and return an Instructor object given a name and [(start,end)] style schedule"""
    avail = []
    for a, b in v:
        a = dateparser.parse(a)
        b = dateparser.parse(b)
        assert a.tzinfo is not None
        assert b.tzinfo is not None
        for dr in slice_date_range(a, b):
            has_overlap = False
            dr1 = dr + datetime.timedelta(hours=3)
            for occ in occupancy:
                if date_range_overlaps(dr, dr1, occ[0], occ[1]):
                    has_overlap = True
                    break
            if not has_overlap:
                avail.append(dr)

    # Pylint seems to think `US()` doesn't exist. It may be dynamically loaded?
    us_holidays = holidays.US()  # pylint: disable=no-member
    avail = [a for a in avail if a not in us_holidays]

    return Instructor(name=k, caps=caps, avail=avail)


def gen_class_and_area_stats(cur_sched, start_date, end_date):
    """Build a map of when each class in the current schedule was last run, plus
    a list of time swhere areas are occupied, within the bounds of start_date and end_date
    """
    exclusions = defaultdict(list)
    area_occupancy = defaultdict(list)
    instructor_occupancy = defaultdict(list)
    for c in cur_sched:
        t = dateparser.parse(c["fields"]["Start Time"]).astimezone(tz)
        pd = c["fields"]["Period (from Class)"][0]
        rec = c["fields"]["Class"][0]

        exclusion_window = [
            t - datetime.timedelta(pd * 30),
            t + datetime.timedelta(pd * 30),
            t # Main date is included for reference
        ]
        if exclusion_window[0] <= end_date or exclusion_window[1] >= start_date:
            exclusions[rec].append(exclusion_window)
        for i in range(c["fields"]["Days (from Class)"][0]):
            ao = [
                t + datetime.timedelta(days=7 * i),
                t
                + datetime.timedelta(
                    days=7 * i, hours=c["fields"]["Hours (from Class)"][0]
                ),
            ]
            if date_range_overlaps(ao[0], ao[1], start_date, end_date):
                area_occupancy[c["fields"]["Name (from Area) (from Class)"][0]].append(
                    ao + [c["fields"]["Name (from Class)"]]
                )
                instructor_occupancy[c["fields"]["Instructor"].lower()].append(ao)
    for v in area_occupancy.values():
        v.sort(key=lambda o: o[1])
    return exclusions, area_occupancy, instructor_occupancy


def filter_same_classday(inst, avail, cur_sched):
    teaching_days = set([
            (dateparser.parse(c['fields']['Start Time']).astimezone(tz) + datetime.timedelta(days=7*d)).date()
            for c in cur_sched
            for d in range(c['fields']['Days (from Class)'][0])
            if c['fields']['Instructor'].lower() == inst.lower()
    ])
    return [a for a in avail if dateparser.parse(a[0]).astimezone(tz).date() not in teaching_days]

def generate_env(
    start_date,
    end_date,
    instructor_filter=None,
    include_proposed=True,
):  # pylint: disable=too-many-locals
    """Generates the environment to be passed to the solver"""

    if instructor_filter is not None:
        instructor_filter = [k.lower() for k in instructor_filter]
        log.info(f"Filter: {instructor_filter}")
    instructor_caps = airtable.fetch_instructor_teachable_classes()
    sched_formatted = fetch_formatted_schedule(instructor_filter, start_date, end_date)
    cur_sched = [
        c
        for c in airtable.get_class_automation_schedule()
        if c["fields"].get("Rejected") is None
    ]
    if not include_proposed:
        cur_sched = [c for c in cur_sched if c["fields"].get("Neon ID") is not None]


    # Filter out any classes that have/will run too recently
    exclusions, area_occupancy, instructor_occupancy = gen_class_and_area_stats(
        cur_sched, start_date, end_date
    )
    log.info(f"Computed exclusion times of {len(exclusions)} different classes")
    log.info(
        f"Computed occupancy of {len(area_occupancy)} different areas, "
        f"{len(instructor_occupancy)} instructors"
    )

    instructors = []
    skipped = 0
    for k, v in sched_formatted.items():
        k = k.lower()
        if instructor_filter is not None and k not in instructor_filter:
            log.debug(f"Skipping instructor {k} (not in filter)")
            continue

        print("Before_filter", v)
        v = filter_same_classday(k, v, cur_sched)
        print("AfteR_filter", v)

        log.debug(f"Handling {k}")
        caps = instructor_caps.get(k, [])
        if len(instructor_caps[k]) == 0:
            log.warning(
                f"Instructor {k} has no capabilities listed in Airtable "
                f"and will be skipped (schedule: {v})"
            )
            skipped += 1
            continue
        instructors.append(
            build_instructor(
                k,
                v,
                caps,
                instructor_occupancy[k],
            )
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
                    c["fields"]["Hours"],
                    c["fields"]["Area"],
                    exclusions[c["id"]],
                    compute_score(c),
                )
            )

    log.info(
        f"Loaded {len(instructors)} instructors and {len(classes)} schedulable classes"
    )
    unavailable = set(instructor_caps.keys()) - {i.name for i in instructors}
    if len(unavailable) > 0 and instructor_filter is None:
        log.warning(
            f"{len(unavailable)} instructor(s) with caps are not "
            f"present in the final list: {unavailable}"
        )

    # Regardless of capabilities, the class must also be set as schedulable
    class_ids = {c.airtable_id for c in classes}
    all_caps = set()
    for i in instructors:
        i.caps = [c for c in i.caps if c in class_ids]
        log.info(f"Adding caps {i.caps}")
        all_caps = all_caps.union(i.caps)

    log.info(f"All capabilities: {all_caps}")
    return {
        "classes": [c.as_dict() for c in classes if c.airtable_id in all_caps],
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
    start = dateparser.parse(date).astimezone(tz)
    return f"- {start.strftime('%A %b %-d, %-I%p')}: {name}"


def push_schedule(sched, autoconfirm=False):
    """Pushes the created schedule to airtable"""
    payload = []
    now = tznow().isoformat()
    email_map = {k.lower(): v for k, v in airtable.get_instructor_email_map().items()}
    for inst, classes in sched.items():
        for record_id, _, date in classes:
            date = dateparser.parse(date)
            if date.tzinfo is None:
                date = tz.localize(date)
            payload.append(
                {
                    "Instructor": inst,
                    "Email": email_map[inst.lower()],
                    "Start Time": date.isoformat(),
                    "Class": [record_id],
                    "Confirmed": now if autoconfirm else None,
                }
            )
    for p in payload:
        airtable.append_classes_to_schedule([p])


def gen_schedule_push_notifications(sched):
    """Generate notifications for scheduling automation when done out of band of instructor"""
    email_map = {k.lower(): v for k, v in airtable.get_instructor_email_map().items()}
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

    return notifications
