"""Methods for scheduling new classes"""

import datetime
import logging
from collections import defaultdict

from dateutil import parser as dateparser

from protohaven_api.automation.classes.solver import (
    Class,
    Instructor,
    expand_recurrence,
    solve,
)
from protohaven_api.automation.classes.validation import (
    date_range_overlaps,
    sort_and_merge_date_ranges,
    validate_candidate_class_time,
)
from protohaven_api.config import get_config, tz, tznow
from protohaven_api.integrations import airtable, booked
from protohaven_api.integrations.airtable_base import _idref, get_all_records
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("class_automation.scheduler")


def get_reserved_area_occupancy(from_date, to_date):
    """Fetches reservations between `from_date` and `to_date` and
    groups them by the area they occupy. This is intended
    to prevent class scheduling automation from colliding with
    manually-scheduled reservations on tools."""
    occupancy = defaultdict(list)
    id_to_area = {}
    for row in get_all_records("tools_and_equipment", "tools"):
        rid = row["fields"].get("BookedResourceId")
        area = row["fields"].get("Name (from Shop Area)")
        if rid and area:
            id_to_area[str(rid)] = area
    for res in booked.get_reservations(from_date, to_date)["reservations"]:
        for area in id_to_area.get(res["resourceId"], []):
            # We use "buffered" start and end date, even though
            # currently it's the same value as start/end date.
            # There may be setup/teardown time incorporated in
            # the future for reservations though.
            occupancy[area].append(
                [
                    dateparser.parse(res["bufferedStartDate"]),
                    dateparser.parse(res["bufferedEndDate"]),
                    f"{res['resourceName']} reservation by "
                    + f"{res['firstName']} {res['lastName']}, "
                    + "https://reserve.protohaven.org/Web/reservation/?rn="
                    + str(res["referenceNumber"]),
                ]
            )
    return occupancy


def fetch_formatted_availability(inst_filter, time_min, time_max):
    """Given a list of instructor names and a time interval,
    return tuples of times bounding their availability"""
    result = {}
    for inst in inst_filter:
        rows = airtable.get_instructor_availability(inst)
        # Have to drop the record IDs
        result[inst] = [
            [t0.isoformat(), t1.isoformat(), row_id]
            for row_id, t0, t1 in sort_and_merge_date_ranges(
                airtable.expand_instructor_availability(rows, time_min, time_max)
            )
        ]
    return result


def slice_date_range(start_date: datetime, end_date: datetime, class_duration: int):
    """Convert all time between two datetime values into a set of
    discrete datetimes marking the potential onset of a class"""
    # Would be best to switch to time-bucketed scheduling that would allow for
    # more variety of classes without hard-constraiing start times to prevent
    # overlaps.
    day_class_hours = [10, 13, 14, 18]
    evening_threshold = 17
    evening_only_days = {0, 1, 2, 3, 4}  # Monday is 0, Sunday is 6
    ret = []
    base_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz)
    for i in range((end_date - start_date).days + 1):
        for j in day_class_hours:
            candidate = base_date + datetime.timedelta(days=i, hours=j)
            if candidate.weekday() in evening_only_days and j < evening_threshold:
                continue  # Some days, we only allow classes to run in the evening
            if (
                candidate >= start_date
                and candidate + datetime.timedelta(hours=class_duration) <= end_date
            ):
                ret.append(candidate)
    return ret


def compute_score(cls):  # pylint: disable=unused-argument
    """Compute an integer score based on a class' desirability to run"""
    return 1.0  # Improve this later


def build_instructor(  # pylint: disable=too-many-locals,too-many-arguments
    name, avail, caps, instructor_occupancy, area_occupancy, class_by_id
):
    """Create and return an Instructor object for use in the solver"""
    candidates = defaultdict(list)
    rejected = defaultdict(list)
    if len(caps) == 0:
        rejected["Instructor Validation"].append(
            {
                "time": None,
                "reason": "Instructor has no capabilities listed - "
                "please contact an education lead.",
            }
        )
        return Instructor(name, candidates, rejected)

    # Convert instructor-provided availability ranges into discrete "class at time" candidates,
    # making notes on which candidates are rejected and why
    avail = [[dateparser.parse(a).astimezone(tz) for a in aa[:2]] for aa in avail]
    for t0, t1 in avail:
        for c in caps:
            cbid = class_by_id.get(c)
            if not cbid:
                rejected["Availability Validation"].append(
                    {
                        "time": None,
                        "reason": f"Could not find class info in Airtable (id {c})",
                    }
                )
                continue
            sliced = slice_date_range(t0, t1, cbid.hours)
            if len(sliced) == 0:
                rejected["Availability Validation"].append(
                    {
                        "time": t0.isoformat(),
                        "reason": "Available time does not include one of the scheduler's "
                        "allowed class times (e.g. weekdays 6pm-9pm, see wiki for details)",
                    }
                )
                continue

            for start in sliced:
                valid, reason = validate_candidate_class_time(
                    cbid, start, instructor_occupancy, area_occupancy, avail
                )
                if not valid:
                    rejected[c].append({"time": t0.isoformat(), "reason": reason})
                else:
                    candidates[c].append(start)

    candidates = dict(candidates)

    # Append empty lists for remaining capabilities,
    # to indicate we have that capability but no scheduling window
    for c in caps:
        if c not in candidates:
            candidates[c] = []

    return Instructor(name, candidates, dict(rejected))


def gen_class_and_area_stats(
    cur_sched, start_date, end_date, clearance_code_mapping, reserved_areas
):  # pylint: disable=too-many-locals
    """Build a map of when each class in the current schedule was last run, plus
    a list of times where areas are occupied, within the bounds of start_date and end_date
    """
    exclusions = defaultdict(list)
    clearance_exclusion = defaultdict(list)
    area_occupancy = defaultdict(list)
    instructor_occupancy = defaultdict(list)
    clearance_exclusion_range = get_config(
        "general/class_scheduling/clearance_exclusion_range_days"
    )

    for c in cur_sched:
        t = dateparser.parse(c["fields"]["Start Time"]).astimezone(tz)
        pd = (c["fields"].get("Period (from Class)") or [None])[0]
        if not pd:
            log.warning(f"Class missing template info: {c}")
            continue
        rec = _idref(c, "Class")[0]

        dates = list(
            expand_recurrence(
                (c["fields"].get("Recurrence (from Class)") or [None])[0],
                c["fields"]["Hours (from Class)"][0],
                t,
            )
        )

        # Repeats of the class are excluded based on the start and end run date
        exclusion_window = [
            dates[0][0] - datetime.timedelta(days=pd),
            dates[-1][0] + datetime.timedelta(days=pd),
            t,  # Main date is included for reference
        ]

        # Clearances are excluded only based on start date
        clearance_exclusion_window = [
            dates[0][0] - datetime.timedelta(days=clearance_exclusion_range),
            dates[0][0] + datetime.timedelta(days=clearance_exclusion_range),
            t,  # Main date is included for reference
        ]
        if exclusion_window[0] <= end_date or exclusion_window[1] >= start_date:
            exclusions[rec].append(exclusion_window)
        if (
            clearance_exclusion_window[0] <= end_date
            or clearance_exclusion_window[1] >= start_date
        ):
            for clr in c["fields"].get("Clearance (from Class)") or []:
                mapped = clearance_code_mapping.get(clr)
                if mapped:
                    clearance_exclusion[mapped].append(clearance_exclusion_window)

        for t0, t1 in dates:
            if date_range_overlaps(t0, t1, start_date, end_date):
                aoc = [
                    t0,
                    t1,
                    c["fields"]["Name (from Class)"],
                ]  # Include class name for later reference
                area_occupancy[c["fields"]["Name (from Area) (from Class)"][0]].append(
                    aoc
                )
                instructor_occupancy[c["fields"]["Instructor"].lower()].append(aoc)

    # Also pull in data from Booked scheduler to prevent overlap with manual reservations
    for area, aocs in reserved_areas.items():
        area_occupancy[area] += aocs

    for v in area_occupancy.values():
        v.sort(key=lambda o: o[1])
    return exclusions, area_occupancy, clearance_exclusion, instructor_occupancy


def load_schedulable_classes(class_exclusions, clearance_exclusions):
    """Load all classes which are schedulable, as Class instances.
    If there's anything that requires the instructor's attention, it's
    appended to a list of notes as part of the return value.
    """
    classes = []
    notices = defaultdict(list)
    for c in airtable.get_all_class_templates():
        if c["fields"].get("Schedulable") is True:
            missing = [
                f for f in ("Name", "Hours", "Name (from Area)") if f not in c["fields"]
            ]
            if len(missing) > 0:
                notices[c["id"]].append(
                    f"{c['fields']['Name']} template missing required fields: {', '.join(missing)} "
                    "- cannot schedule; contact an Edu Lead to resolve this"
                )
                continue
            if not c["fields"].get("Image Link"):
                notices[c["id"]].append(
                    "Class is missing a promo image - registrations will suffer. Reach out "
                    "in the #instructors Discord channel or to "
                    "education@protohaven.org."
                )

            exclusions = [ee + ["class"] for ee in class_exclusions.get(c["id"], [])]
            exclusions += [
                ee + [f"clearance ({clr})"]
                for clr in _idref(c, "Clearance")
                for ee in (clearance_exclusions.get(clr) or [])
            ]
            classes.append(
                Class(
                    str(c["id"]),
                    c["fields"]["Name"],
                    hours=c["fields"]["Hours"],
                    recurrence=c["fields"].get("Recurrence") or None,
                    areas=c["fields"]["Name (from Area)"],
                    exclusions=exclusions,
                    score=compute_score(c),
                )
            )
    return classes, notices


def generate_env(
    start_date,
    end_date,
    instructor_filter=None,
    include_proposed=True,
):  # pylint: disable=too-many-locals
    """Generates the environment to be passed to the solver"""

    # Load instructor capabilities  and availability
    if instructor_filter is not None:
        instructor_filter = [k.lower() for k in instructor_filter]
        log.info(f"Filter: {instructor_filter}")
    instructor_caps = airtable.fetch_instructor_teachable_classes()
    avail_formatted = fetch_formatted_availability(
        instructor_filter, start_date, end_date
    )

    cur_sched = [
        c
        for c in airtable.get_class_automation_schedule()
        if c["fields"].get("Rejected") is None
    ]
    if not include_proposed:
        cur_sched = [c for c in cur_sched if c["fields"].get("Neon ID") is not None]

    reserved_areas = get_reserved_area_occupancy(start_date, end_date)
    log.info(f"Computed reservations for {len(reserved_areas)} area(s)")

    # Compute ancillary info about what times/areas/instructors are occupied by which classes

    clearance_code_mapping = {
        rec["id"]: rec["fields"].get("Code")
        for rec in airtable.get_all_records("class_automation", "clearance_codes")
    }

    (
        exclusions,
        area_occupancy,
        clearance_exclusions,
        instructor_occupancy,
    ) = gen_class_and_area_stats(
        cur_sched, start_date, end_date, clearance_code_mapping, reserved_areas
    )
    log.info(
        f"Computed exclusion times of {len(exclusions)} different classes, "
        f"{len(clearance_exclusions)} clearances"
    )
    log.info(
        f"Computed occupancy of {len(area_occupancy)} different areas, "
        f"{len(instructor_occupancy)} instructors"
    )

    # Load classes from airtable
    classes, notices = load_schedulable_classes(exclusions, clearance_exclusions)
    class_by_id = {c.class_id: c for c in classes}
    log.info(f"Loaded {len(classes)} classes")

    instructors = []
    skipped = 0
    for k, v in avail_formatted.items():
        k = k.lower()
        if instructor_filter is not None and k not in instructor_filter:
            log.debug(f"Skipping instructor {k} (not in filter)")
            continue

        caps = instructor_caps.get(k, [])
        if len(instructor_caps[k]) == 0:
            log.warning(
                f"Instructor {k} has no capabilities listed in Airtable "
                f"and will be skipped (schedule: {v})"
            )
            skipped += 1
            continue

        inst_occ = instructor_occupancy.get(k) or []
        instructors.append(
            build_instructor(
                k,
                v,
                caps,
                inst_occ,
                area_occupancy,
                class_by_id,
            )
        )

    if skipped > 0:
        log.warning(
            f"Direct the {skipped} instructor(s) missing capabilities "
            "to this form to submit them: https://airtable.com/applultHGJxHNg69H/shr5VVjEbKd0a1DIa"
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
    all_inst_caps = set()
    for i in instructors:
        all_inst_caps = all_inst_caps.union(i.caps)

    log.info(f"All capabilities: {all_inst_caps}")
    return {
        "classes": [c.as_dict() for c in classes if c.class_id in all_inst_caps],
        "notices": notices,
        "instructors": [i.as_dict() for i in instructors],
        "area_occupancy": dict(
            area_occupancy.items()
        ),  # Convert defaultdict to dict for yaml serialization
    }


def solve_with_env(env):
    """Solves a scheduling problem given a specific env"""
    classes = [Class(**c) for c in env["classes"]]
    instructors = [Instructor(**i) for i in env["instructors"]]
    return solve(classes, instructors)


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
                date = date.astimezone(tz)
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
        log.info(f"Append classes to schedule: {p}")
        status, content = airtable.append_classes_to_schedule([p])
        if status != 200:
            raise RuntimeError(content)


def gen_schedule_push_notifications(sched):
    """Generate notifications for scheduling automation when done out of band of instructor"""
    if sched:
        email_map = {
            k.lower(): v for k, v in airtable.get_instructor_email_map().items()
        }
        for inst, classes in sched.items():
            classes.sort(key=lambda c: c[2])
            formatted = [format_class(f) for f in classes]
            yield Msg.tmpl(
                "schedule_push_notification",
                title=inst.title(),
                target=email_map[inst],
                formatted=formatted,
            )
