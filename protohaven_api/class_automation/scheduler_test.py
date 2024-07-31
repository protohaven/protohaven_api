"""Test operation of linear solver for class scheduling"""
# pylint: skip-file

import datetime

import pytz
from dateutil.parser import parse as parse_date

from protohaven_api.class_automation import scheduler as s
from protohaven_api.config import tz, tznow


def d(i, h=0):
    """Returns a date based on an integer, for testing"""
    return datetime.datetime(year=2025, month=1, day=1) + datetime.timedelta(
        days=i, hours=h
    )


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
        "testname", [("2024-04-01T18:00:00-04:00", "2024-04-01T21:00:00-04:00")], [], []
    ).avail == [parse_date("2024-04-01T18:00:00-04:00")]


def test_build_instructor_respects_occupancy():
    assert (
        s.build_instructor(
            "testname",
            [("2024-04-01T18:00:00-05:00", "2024-04-01T21:00:00-05:00")],
            [],
            [
                [
                    parse_date("2024-04-01T19:00:00-04:00"),
                    parse_date("2024-04-01T22:00:00-04:00"),
                ]
            ],
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


def test_gen_class_and_area_stats_exclusions():
    """Verify that exclusions account for the time before and after a run of a class
    that should be avoided when schedling new classes"""
    exclusions, _, _ = s.gen_class_and_area_stats(
        [
            {
                "fields": {
                    "Start Time": "2024-04-01",
                    "Class": ["r1"],
                    "Days (from Class)": [0],
                    "Period (from Class)": [1],
                }
            },
            {
                "fields": {
                    "Start Time": "2024-03-01",
                    "Class": ["r1"],
                    "Days (from Class)": [0],
                    "Period (from Class)": [1],
                }
            },
        ],
        parse_date("2024-02-01T00:00:00-04:00"),
        parse_date("2024-05-01T00:00:00-05:00"),
    )
    assert [tuple([d.strftime("%Y-%m-%d") for d in dd]) for dd in exclusions["r1"]] == [
        ("2024-03-02", "2024-05-01", "2024-04-01"),
        ("2024-01-31", "2024-03-31", "2024-03-01"),
    ]


def test_filter_same_classday():
    got = s.filter_same_classday(
        "inst",
        [(d(i * 7, 16).isoformat(), None) for i in range(4)],
        [
            {
                "fields": {
                    "Start Time": d(7, 12).isoformat(),
                    "Days (from Class)": [2],
                    "Instructor": "inst",
                }
            },
            {
                "fields": {
                    "Start Time": d(0, 12).isoformat(),
                    "Days (from Class)": [1],
                    "Instructor": "ignored",
                }
            },
        ],
    )
    assert got == [(d(i, 16).isoformat(), None) for i in (0, 21)]


def test_fetch_formatted_availability(mocker):
    mocker.patch.object(
        s.airtable,
        "get_instructor_availability",
        return_value=[
            {
                "id": "rowid",
                "fields": {
                    "Instructor (from Instructor)": "foo",
                    "Start": d(0, 16).isoformat(),
                    "End": d(0, 19).isoformat(),
                    "Recurrence": "RRULE:FREQ=DAILY",
                },
            }
        ],
    )
    got = s.fetch_formatted_availability(["foo"], d(0), d(2, 0))
    assert got == {
        "foo": [
            [d(0, 16).isoformat(), d(0, 19).isoformat()],
            [d(1, 16).isoformat(), d(1, 19).isoformat()],
        ]
    }
