"""Provide date and availability validation methods for class scheduling"""

import datetime
import logging
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass

import holidays

from protohaven_api.automation.techs.techs import ph_holidays
from protohaven_api.config import safe_parse_datetime, truncate_date, tz
from protohaven_api.integrations.airtable import (
    AreaID,
    Class,
    InstructorID,
    Interval,
    RecordID,
)

log = logging.getLogger("automation.classes.validation")

type Datetime = datetime.datetime
type StrInterval = tuple[str, str]
type NamedInterval = tuple[Datetime, Datetime, str]
type NamedStrInterval = tuple[str, str, str]


@dataclass
class Exclusion:
    """Indicates a window of exclusion based on a different event"""

    start: datetime.datetime
    end: datetime.datetime
    main_date: datetime.datetime
    origin: str


@dataclass
class ClassAreaEnv:
    exclusions: dict[RecordID, list[Exclusion]]
    clearance_exclusions: dict[RecordID, list[Exclusion]]
    area_occupancy: dict[AreaID, list[NamedInterval]]
    instructor_occupancy: dict[InstructorID, list[NamedInterval]]

    @classmethod
    def with_defaults(cls):
        return cls(
            defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
        )


def str_interval_to_interval(ii: list[StrInterval | Interval]) -> list[Interval]:
    """Coalesce string dates into actual datetime objects"""
    if len(ii) > 0 and isinstance(ii[0][0], str):
        # Convert from string to Date if required
        return [[*[safe_parse_datetime(e) for e in ee[:-1]], ee[-1]] for ee in ii]
    return ii


def date_range_overlaps(a0: Datetime, a1: Datetime, b0: Datetime, b1: Datetime) -> bool:
    """Return True if [a0,a1] and [b0,b1] overlap"""
    assert a0 <= a1 and b0 <= b1
    if b0 <= a0 < b1:
        return True
    if b0 < a1 <= b1:
        return True
    if a0 <= b0 and a1 >= b1:
        return True
    return False


def has_area_conflict(
    area_occupancy: list[NamedInterval], t_start: Datetime, t_end: Datetime
) -> str | bool:
    """Return name of class if any of `area_occupancy` lie
    within `t_start` and `t_end`, false otherwise"""
    for a_start, a_end, name in area_occupancy:
        if date_range_overlaps(a_start, a_end, t_start, t_end):
            return name
    return False


def date_within_exclusions(d, exclusions: list[Exclusion]) -> Exclusion | bool:
    """Returns the matching exclusion date if `d` is
    within any of the tuples in the list of `exclusions`"""
    for e in exclusions:
        if e.start <= d <= e.end:
            return e
    return False


def overlapping(c1: list[Interval], c2: list[Interval]) -> bool:
    """Expand two classes starting at two times and return
    True if they overlap
    """
    for t10, t11 in c1:
        for t20, t21 in c2:
            if date_range_overlaps(t10, t11, t20, t21):
                return True
    return False


def get_overlapping_by_time(
    i: Interval, classes: Iterator[Class]
) -> Iterator[NamedInterval]:
    """Yields a sequence of (class_id, start_time) of classes that would
    conflict with class `c1` running at time `t1`.
    Note that duplicate values may be returned."""
    for c2 in classes:
        t10, t11 = i
        for t20, t21 in c2.sessions:
            if date_range_overlaps(t10, t11, t20, t21):
                yield (t20, t21, c2.class_id)


def get_overlapping_by_area(
    a: set[AreaID], i: Interval, classes: Iterator[Class]
) -> Iterator[NamedInterval]:
    """Yields a sequence of NamedInterval  of classes that would
    conflict with class `c1` running at time `t1` in the same area.
    Note that duplicate values may be returned."""
    for c2 in classes:
        # Classes without intersecting areas don't have a chance of overlapping
        if len(a.intersection(set(c2.areas))) == 0:
            continue
        t10, t11 = i
        for t20, t21 in c2.sessions:
            if date_range_overlaps(t10, t11, t20, t21):
                yield (t20, t21, c2.class_id)


# Pylint seems to think `US()` doesn't exist. It may be dynamically loaded?
us_holidays = holidays.US()  # pylint: disable=no-member


def validate_candidate_class_session(  # pylint: disable=too-many-return-statements, too-many-locals
    inst: InstructorID, i: Interval, c: Class, env: ClassAreaEnv
) -> tuple[bool, str]:
    """Ensure solver.Class `c` being taught at `start` is not invalid for reasons e.g.
    - Scheduled on a US holiday
    - On the same day as instructor is already teaching (`inst_occupancy`)
    - In an area that's already reserved for something else (`area_occupancy`)
    - Too soon before/after the same class is already scheduled (c.exclusions)
    """

    t0, t1 = i

    # Prevent if interval is not sufficient for a session
    duration = (t1 - t0).seconds
    if duration != c.hours * 3600:
        return False, f"duration is {duration/3600}h, want {c.hours}h"

    # Prevent scheduling outside of Protohaven business hours
    # Note that we base both open and close time on t0 to prevent
    # overnight oopsies
    topen = truncate_date(t0, hour=10)
    tclose = truncate_date(t0, hour=22)
    if not topen <= t0 <= tclose:
        return False, "Start time is outside of business hours (10am-10pm)"
    if not topen <= t1 <= tclose:
        return (
            False,
            "End date is outside of business hours (10am-10pm, same day as starting date)",
        )

    # Prevent holiday classes
    if t0 in us_holidays:
        return False, f"Occurs on a US holiday ({us_holidays.get(t0)})"
    if t0 in ph_holidays:
        return False, f"Occurs on a Protohaven holiday ({ph_holidays.get(t0)})"

    # Prevent if instructor is already busy on this day
    for occ in env.instructor_occupancy.get(inst) or []:
        if t0.date() == occ[0].date():
            return (
                False,
                f"Same day as another class you're teaching ({occ[2]})",
            )

    # Prevent if area is already occupied
    for a in c.areas:
        conflict = has_area_conflict(env.area_occupancy.get(a, []), t0, t1)
        if conflict:
            return (
                False,
                f"Area already occupied ({conflict})",
            )

    # Prevent this particular time if it's in an exclusion region
    log.info(f"Exclusions for {c.class_id}: {env.exclusions}")
    excluding_class_dates = date_within_exclusions(t0, env.exclusions[c.class_id])
    if excluding_class_dates:
        return (
            False,
            f"Too soon before/after same {excluding_class_dates.origin} (scheduled for "
            f"{excluding_class_dates.main_date.strftime('%Y-%m-%d')}; no repeats allowed "
            f"between {excluding_class_dates.start.strftime('%Y-%m-%d')} and "
            f"{excluding_class_dates.end.strftime('%Y-%m-%d')})",
        )

    return True, ""
