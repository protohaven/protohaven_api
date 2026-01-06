"""Methods for scheduling new classes"""

import datetime
import logging
from collections import defaultdict

from protohaven_api.automation.classes import validation as val
from protohaven_api.automation.classes.validation import ClassAreaEnv
from protohaven_api.config import get_config, safe_parse_datetime, tznow
from protohaven_api.integrations import airtable, booked
from protohaven_api.integrations.airtable import (
    AreaID,
    InstructorID,
    Interval,
    RecordID,
)
from protohaven_api.integrations.airtable_base import get_all_records
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("class_automation.scheduler")


def get_reserved_area_occupancy(
    from_date: datetime.datetime, to_date: datetime.datetime
) -> dict[AreaID, list[val.NamedInterval]]:
    """Fetches reservations between `from_date` and `to_date` and
    groups them by the area they occupy. This is intended
    to prevent class scheduling automation from colliding with
    manually-scheduled reservations on tools."""
    occupancy = defaultdict(list)
    id_to_area = {}
    for row in get_all_records("tools_and_equipment", "tools"):
        rid = row["fields"].get("BookedResourceId")
        area: AreaID = row["fields"].get("Name (from Shop Area)")
        if rid and area:
            id_to_area[str(rid)] = area
    for res in booked.get_reservations(from_date, to_date)["reservations"]:
        for area in id_to_area.get(res["resourceId"], []):
            # We use "buffered" start and end date, even though
            # currently it's the same value as start/end date.
            # There may be setup/teardown time incorporated in
            # the future for reservations though.
            occupancy[area].append(
                (
                    res["bufferedStartDate"],
                    res["bufferedEndDate"],
                    f"{res['resourceName']} reservation by "
                    + f"{res['firstName']} {res['lastName']}, "
                    + "https://reserve.protohaven.org/Web/reservation/?rn="
                    + str(res["referenceNumber"]),
                )
            )
    return dict(occupancy)


def gen_class_and_area_stats(  # pylint: disable=too-many-locals
    start_date: datetime.datetime,
    end_date: datetime.datetime,
) -> ClassAreaEnv:
    """Build a map of when each class in the current schedule was last run, plus
    a list of times where areas are occupied, within the bounds of start_date and end_date
    """
    env = ClassAreaEnv.with_defaults()
    clearance_exclusion_range = datetime.timedelta(
        days=get_config("general/class_scheduling/clearance_exclusion_range_days")
    )

    for c in airtable.get_class_automation_schedule(include_rejected=False, raw=False):
        if not c.period:
            log.warning(f"Class missing template info: {c}")
            continue

        # Repeats of the class are excluded based on the start and end run date
        first = c.sessions[0][0]
        last = c.sessions[-1][0]
        exclusion_window = val.Exclusion(
            start=first - c.period,
            end=last + c.period,
            main_date=first,
            origin=c.name,
        )
        if exclusion_window.start <= end_date or exclusion_window.end >= start_date:
            log.info(f"Adding class ID {c.class_id} exclusions {exclusion_window}")
            env.exclusions[c.class_id].append(exclusion_window)

        # Clearances are excluded only based on start date, i.e. when a member
        # would have been able to register for the clearance
        clearance_exclusion_window = val.Exclusion(
            start=first - clearance_exclusion_range,
            end=first + clearance_exclusion_range,
            main_date=first,  # Main date is included for reference
            origin=c.name,
        )
        if (
            clearance_exclusion_window.start <= end_date
            or clearance_exclusion_window.end >= start_date
        ):
            for clr in c.clearances:
                env.clearance_exclusions[clr].append(clearance_exclusion_window)

        for t0, t1 in c.sessions:
            if val.date_range_overlaps(t0, t1, start_date, end_date):
                aoc: val.NamedInterval = (t0, t1, c.name)
                for area in c.areas:
                    env.area_occupancy[area].append(aoc)
                env.instructor_occupancy[c.instructor_email].append(aoc)

    # Also pull in data from Booked scheduler to prevent overlap with manual reservations
    for area, aocs in get_reserved_area_occupancy(start_date, end_date).items():
        env.area_occupancy[area] += aocs
    for v in env.area_occupancy.values():
        v.sort(key=lambda o: o[1])

    log.info(
        f"Computed exclusion times of {len(env.exclusions)} different classes, "
        f"{len(env.clearance_exclusions)} clearances"
    )
    log.info(
        f"Computed occupancy of {len(env.area_occupancy)} different areas, "
        f"{len(env.instructor_occupancy)} instructors"
    )

    return env


def _fmt_date(d):
    return d.strftime("%m/%d/%Y %-I:%M %p")


def validate(  # pylint: disable=too-many-branches, too-many-locals
    inst_id: InstructorID, cls_id: RecordID, sessions: list[val.Interval]
) -> list[str]:
    """Validates a given class to make sure it doesn't conflict with anything"""

    # ============= Basic validation of teachability ===================
    c = airtable.get_class_template(cls_id)
    if not c:
        return [f"Class not found ({cls_id})"]
    if not c.approved:
        return [f"Class not approved ({cls_id})"]
    if not c.schedulable:
        return [f"Class not schedulable ({cls_id})"]
    log.info(f"{inst_id} vs approved instructors: {c.approved_instructors}")
    if not inst_id in c.approved_instructors:
        return [f"You are not assigned to teach this class ({cls_id})"]

    # ============== Gathering data for detailed timing checks =============
    # Time boundary for searching for reservations etc.
    start_date = min(t for tt in sessions for t in tt)
    end_date = max(t for tt in sessions for t in tt)
    env: ClassAreaEnv = gen_class_and_area_stats(start_date, end_date)

    # ============ Validate timing of the class ==============
    errors = []
    if len(sessions) != c.days:
        errors.append(
            f"{len(sessions)}d of sessions not sufficient for {c.days}d class"
        )
    else:
        for i in range(len(sessions) - 1):
            if (sessions[i + 1][0] - sessions[i][0]).total_seconds() / (24 * 3600) > 10:
                errors.append(
                    f"More than 10 days between sessions {sessions[i][0]} and {sessions[i+1][0]}"
                )

    for t1, t2 in sessions:
        if t1 >= t2:
            errors.append(f"Session start ({t1}) must be before session end ({t2})")
    if sorted(sessions, key=lambda t: t[0]) != sessions:
        errors.append("Sessions must be in chronological order")

    for i, s1 in enumerate(sessions):
        for s2 in sessions[i + 1 :]:
            if val.date_range_overlaps(*s1, *s2):
                errors.append(
                    f"Overlapping sessions {_fmt_date(s1[0])} and {_fmt_date(s2[0])}"
                )

    for i, tt in enumerate(sessions):
        valid, reason = val.validate_candidate_class_session(inst_id, tt, c, env)
        if not valid:
            errors.append(f"{_fmt_date(tt[0])}: {reason}")

    return errors


def format_class(cls):
    """Convert a class into bulleted representation, for email summary"""
    _, name, date = cls
    start = safe_parse_datetime(date)
    return f"- {start.strftime('%A %b %-d, %-I%p')}: {name}"


def push_class_to_schedule(
    inst_id: InstructorID, cls_id: RecordID, sessions: list[Interval]
):
    """Pushes the created schedule to airtable"""
    name_map = {v.lower(): k for k, v in airtable.get_instructor_email_map().items()}
    payload = {
        "Instructor": name_map.get(inst_id.lower().strip()),
        "Email": inst_id.strip().lower(),
        "Sessions": ",".join([ss[0].isoformat() for ss in sessions]),
        "Class": [cls_id],
        "Confirmed": tznow().isoformat(),
    }
    log.info(f"Append class to schedule: {payload}")
    status, content = airtable.append_classes_to_schedule([payload])
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
