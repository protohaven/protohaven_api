"""Test operation of linear solver for class scheduling"""
# pylint: skip-file

import datetime

import pytz
from dateutil.parser import parse as parse_date

from protohaven_api.class_automation import scheduler as s
from protohaven_api.config import tz, tznow


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


def test_slice_date_range():
    """Slices date range into individual start times"""
    assert s.slice_date_range(t(9, weekday=6), t(14, weekday=6)) == [
        t(10, weekday=6)
    ]  # Loose bounds
    assert s.slice_date_range(t(10, weekday=6), t(13, weekday=6)) == [
        t(10, weekday=6)
    ]  # Tight bounds still work
    assert not s.slice_date_range(
        t(10, weekday=6), t(12, weekday=6)
    )  # Too tight for a 3 hour class
    assert s.slice_date_range(t(9, weekday=0), t(22, weekday=0)) == [
        t(18, weekday=0)
    ]  # Only weekday evenings allowed


def test_slice_date_range_tzinfo():
    """Confirm daylight savings is observed for US/Eastern, regardless of incoming time zone info"""
    tz2 = pytz.timezone("EST")  # Force incorrect DST on input dates
    pre_dst = s.slice_date_range(
        datetime.datetime(year=2024, month=3, day=4, hour=00, tzinfo=tz2),
        datetime.datetime(year=2024, month=3, day=5, hour=23, tzinfo=tz2),
    )[0]
    post_dst = s.slice_date_range(
        datetime.datetime(year=2024, month=3, day=12, hour=00, tzinfo=tz2),
        datetime.datetime(year=2024, month=3, day=14, hour=23, tzinfo=tz2),
    )[1]
    assert [
        pre_dst.isoformat().rsplit("-")[-1],
        post_dst.isoformat().rsplit("-")[-1],
    ] == ["05:00", "04:00"]


def test_generate_schedule_data():
    """Properly generates data for scheduler to run on"""
    # holiday = datetime.datetime(year=2024, month=7, day=4, hour=7, tzinfo=tz)
    # assert holiday in holidays.US()
    # assert slice_date_range(holiday, holiday.replace(hour=22)) == [] # Holidays are excluded


def test_build_instructor():
    assert s.build_instructor(
        "testname", [("2024-04-01 6pm EST", "2024-04-01 9pm EST")], None, None, []
    ).avail == [parse_date("2024-04-01 6pm EST")]


def test_build_instructor_respects_occupancy():
    assert (
        s.build_instructor(
            "testname",
            [("2024-04-01 6pm EST", "2024-04-01 9pm EST")],
            None,
            None,
            [[parse_date("2024-04-01 7pm EST"), parse_date("2024-04-01 10pm EST")]],
        ).avail
        == []
    )


def test_push_schedule(mocker):
    mocker.patch.object(s.airtable, "append_classes_to_schedule")
    mocker.patch.object(
        s.airtable,
        "get_instructor_email_map",
        return_value={"test instructor": "a@b.com"},
    )
    now = tznow()
    mocker.patch.object(s, "tznow", return_value=now)
    s.push_schedule(
        {"Test Instructor": [["record0", "Class Name", "5/17/2024, 6:00:00 PM"]]},
        autoconfirm=True,
    )
    s.airtable.append_classes_to_schedule.assert_called_with(
        [
            {
                "Instructor": "Test Instructor",
                "Email": "a@b.com",
                "Start Time": "2024-05-17T18:00:00-04:00",
                "Class": ["record0"],
                "Confirmed": now.isoformat(),
            }
        ]
    )


def test_gen_class_and_area_stats_last_run():
    got, _, _ = s.gen_class_and_area_stats([
        {'fields': {"Start Time": "2024-04-01", "Class": ["r1"], "Days (from Class)": [0]}},
        {'fields': {"Start Time": "2024-03-01", "Class": ["r1"], "Days (from Class)": [0]}},
    ], None, None)
    assert got['r1'] == parse_date("2024-04-01").astimezone(tz)
