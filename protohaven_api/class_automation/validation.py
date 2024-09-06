import datetime

import holidays
from dateutil import parser as dateparser


def date_range_overlaps(a0, a1, b0, b1):
    """Return True if [a0,a1] and [b0,b1] overlap"""
    assert a0 <= a1 and b0 <= b1
    if b0 <= a0 < b1:
        return True
    if b0 < a1 <= b1:
        return True
    if a0 <= b0 and a1 >= b1:
        return True
    return False


def sort_and_merge_date_ranges(aa):
    """Sort and then merge overlapping date ranges to eliminate duplicates"""
    if not isinstance(aa, list):
        aa = list(aa)
    if len(aa) == 0:
        return []
    aa.sort(key=lambda a: a[1])
    last_seen = -1
    for i, a in enumerate(aa):
        if i <= last_seen:
            continue
        a = list(a)
        for j, b in enumerate(aa[i + 1 :], start=i + 1):
            if date_range_overlaps(a[1], a[2], b[1], b[2]):
                a[2] = max(a[2], b[2])
                last_seen = j
        yield a[0], a[1], a[2]


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
            return [e1, e2, esched]
    return False


# Pylint seems to think `US()` doesn't exist. It may be dynamically loaded?
us_holidays = holidays.US()  # pylint: disable=no-member


def validate_candidate_class_time(c, t0, inst_occupancy, area_occupancy):
    """Ensure solver.Class `c` being taught at datetime t0 is not invalid for reasons e.g.
    - Scheduled on a US holiday
    - On the same day as instructor is already teaching (`inst_occupancy`)
    - In an area that's already reserved for something else (`area_occupancy`)
    - Too soon before/after the same class is already scheduled (c.exclusions)
    """
    if c is None or c.hours is None:
        return False, "Could not fetch class timing details"

    # TODO handle multi-day classes (intensives)
    t1 = t0 + datetime.timedelta(hours=c.hours)

    # Skip holiday classes
    if t0 in us_holidays:
        return False, "Occurs on a US holiday"

    # Skip if instructor is already busy on this day
    for occ in inst_occupancy:
        if t0.date() == occ[0].date():
            return (
                False,
                f"Same day as another class being taught by instructor ({occ[2]})",
            )

    # Skip if area is already occupied
    conflict = False
    for a in c.areas:
        conflicting_class = has_area_conflict(area_occupancy.get(a, []), t0, t1)
        if conflicting_class:
            return False, f"Area already occupied by other event ({conflicting_class})"

    # Skip this particular time if it's in an exclusion region
    excluding_class_dates = date_within_exclusions(t0, c.exclusions)
    if excluding_class_dates:
        e1, e2, esched = excluding_class_dates
        return (
            False,
            f"Too soon before/after same class (scheduled for {esched.strftime('%Y-%m-%d')}; no repeats allowed between {e1.strftime('%Y-%m-%d')} and {e2.strftime('%Y-%m-%d')})",
        )

    return True, None
