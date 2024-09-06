"""Helpers for testing code"""

import datetime

from protohaven_api.config import tz


def d(i, h=0):
    """Returns a date based on an integer, for testing"""
    return (datetime.datetime(year=2025, month=1, day=1) + datetime.timedelta(
        days=i, hours=h
    )).astimezone(tz)


def t(hour, weekday=0):
    """Create a datetime object from hour and weekday"""
    return tz.localize(
        datetime.datetime(
            year=2024,
            month=11,
            day=4 + weekday,
            hour=hour,
            minute=0,
            second=0,
        )
    )


def idfn(tc):
    """Extract description from named tuple for parameterization"""
    return tc.desc
