"""Methods for scheduling new classes"""

import datetime
import logging
import traceback
from collections import defaultdict
from dataclasses import dataclass

from protohaven_api.automation.classes import validation as val
from protohaven_api.automation.classes.validation import ClassAreaEnv
from protohaven_api.config import get_config, safe_parse_datetime, tz, tznow
from protohaven_api.integrations import airtable, booked, wiki
from protohaven_api.integrations.airtable import AreaID, InstructorID, RecordID
from protohaven_api.integrations.airtable_base import _idref, get_all_records
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
                [
                    res["bufferedStartDate"],
                    res["bufferedEndDate"],
                    f"{res['resourceName']} reservation by "
                    + f"{res['firstName']} {res['lastName']}, "
                    + "https://reserve.protohaven.org/Web/reservation/?rn="
                    + str(res["referenceNumber"]),
                ]
            )
    return occupancy


def gen_class_and_area_stats(
    start_date: datetime.datetime,
    end_date: datetime.datetime,
) -> ClassAreaEnv:  # pylint: disable=too-many-locals
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
        exclusion_window = val.Exclusion(
            start=c.sessions[0][0] - c.period,
            end=c.sessions[-1][0] + c.period,
            main_date=t,
            origin=c.name,
        )
        if exclusion_window.start <= end_date or exclusion_window.end >= start_date:
            env.exclusions[c.class_id].append(exclusion_window)

        # Clearances are excluded only based on start date, i.e. when a member
        # would have been able to register for the clearance
        clearance_exclusion_window = val.Exclusion(
            start=c.sessions[0][0] - clearance_exclusion_range,
            end=c.sessions[0][0] + clearance_exclusion_range,
            main_date=t,  # Main date is included for reference
            origin=c.name,
        )
        if (
            clearance_exclusion_window[0] <= end_date
            or clearance_exclusion_window[1] >= start_date
        ):
            for clr in c.clearances:
                clearance_exclusion[mapped].append(clearance_exclusion_window)

        for t0, t1 in c.sessions:
            if val.date_range_overlaps(t0, t1, start_date, end_date):
                aoc: NamedInterval = (t0, t1, c.name)
                for area in c.areas:
                    env.area_occupancy[area].append(aoc)
                env.instructor_occupancy[c.instructor].append(aoc)

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


def validate(
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

    for i, tt in enumerate(sessions):
        valid, reason = val.validate_candidate_class_session(tt, c, env)
        if not valid:
            errors.append(f"{tt[0].strftime('%m/%d/%Y %-I:%M %p')}: {reason}")

    return errors


def format_class(cls):
    """Convert a class into bulleted representation, for email summary"""
    _, name, date = cls
    start = safe_parse_datetime(date)
    return f"- {start.strftime('%A %b %-d, %-I%p')}: {name}"


def push_schedule(sched, autoconfirm=False):
    """Pushes the created schedule to airtable"""
    payload = []
    now = tznow().isoformat()
    email_map = {k.lower(): v for k, v in airtable.get_instructor_email_map().items()}
    for inst, classes in sched.items():
        for record_id, _, date in classes:
            date = safe_parse_datetime(date)
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
