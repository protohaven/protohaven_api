"""Test operation of linear solver for class scheduling"""

import datetime

from protohaven_api.class_automation import scheduler


def t(hour, weekday=0):
    """Create a datetime object from hour and weekday"""
    return datetime.datetime(
        year=2024,
        month=11,
        day=4 + weekday,
        hour=hour,
        minute=0,
        second=0,
        tzinfo=scheduler.tz,
    )


def test_slice_date_range():
    """Slices date range into individual start times"""
    assert scheduler.slice_date_range(t(9, weekday=6), t(14, weekday=6)) == [
        t(10, weekday=6)
    ]  # Loose bounds
    assert scheduler.slice_date_range(t(10, weekday=6), t(13, weekday=6)) == [
        t(10, weekday=6)
    ]  # Tight bounds still work
    assert not scheduler.slice_date_range(
        t(10, weekday=6), t(12, weekday=6)
    )  # Too tight for a 3 hour class
    assert scheduler.slice_date_range(t(9, weekday=0), t(22, weekday=0)) == [
        t(18, weekday=0)
    ]  # Only weekday evenings allowed


def test_generate_schedule_data():
    """Properly generates data for scheduler to run on"""
    # holiday = datetime.datetime(year=2024, month=7, day=4, hour=7, tzinfo=tz)
    # assert holiday in holidays.US()
    # assert slice_date_range(holiday, holiday.replace(hour=22)) == [] # Holidays are excluded
