"""Test operation of linear solver for class scheduling"""
# pylint: skip-file

import datetime

import pytz
from dateutil.parser import parse as parse_date

from protohaven_api.class_automation import scheduler as s
from protohaven_api.class_automation.solver import Class
from protohaven_api.config import tz, tznow
from protohaven_api.testing import d, t


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


def test_build_instructor_basic():
    """Test that given nominal data, an Instructor is built and returned OK."""
    TEST_CLASS = Class("test_id", "Test Class", 3, areas=["a0"], exclusions=[[d(5), d(10), d(7)]], score=1.0)
    assert s.build_instructor(
        name="testname", 
        v=[[d(1, 18).isoformat(), d(1, 21).isoformat(), "avail_id"]], 
        caps=[TEST_CLASS.airtable_id], 
        instructor_occupancy=[],
        area_occupancy={},
        class_by_id={TEST_CLASS.airtable_id: TEST_CLASS},
    ).avail == [d(1, 18)]


def test_build_instructor_respects_empty_caps():
    """Capabilities are still listed even when we have no candidate dates"""
    assert s.build_instructor(
        name="testname", 
        v=[], 
        caps=["test_cap"], 
        instructor_occupancy=[],
        area_occupancy={},
        class_by_id={},
    ).caps == ["test_cap"]


def test_build_instructor_daterange_not_supported():
    """Test that rejected candidates for class/time are returned when the instructor has availability"""
    TEST_CLASS = Class("test_id", "Test Class", 3, areas=["a0"], exclusions=[[d(5), d(10), d(7)]], score=1.0)
    inst = s.build_instructor(
        name="testname", 
        v=[[d(1, 12).isoformat(), d(1, 14).isoformat(), "avail_id"]], 
        caps=[],  # <--- no capabilities!
        instructor_occupancy=[],
        area_occupancy={},
        class_by_id={TEST_CLASS.airtable_id: TEST_CLASS},
    )
    assert inst.avail == []
    assert 'Availability range does not include one of the scheduler\'s allowed class times' in inst.rejected["avail_id"][0][2]

def test_build_instructor_no_caps():
    """If instructor has no capabilities, it is mentioned in `rejected`"""
    TEST_CLASS = Class("test_id", "Test Class", 3, areas=["a0"], exclusions=[[d(5), d(10), d(7)]], score=1.0)
    inst = s.build_instructor(
        name="testname", 
        v=[[d(1, 18).isoformat(), d(1, 21).isoformat(), "avail_id"]], 
        caps=[],  # <--- no capabilities!
        instructor_occupancy=[],
        area_occupancy={},
        class_by_id={TEST_CLASS.airtable_id: TEST_CLASS},
    )
    assert inst.avail == []
    assert 'Instructor has no capabilities listed' in inst.rejected["avail_id"][0][2]


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
            [d(0, 16).isoformat(), d(0, 19).isoformat(), "rowid"],
            [d(1, 16).isoformat(), d(1, 19).isoformat(), "rowid"],
        ]
    }
