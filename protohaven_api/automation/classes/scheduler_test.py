"""Test operation of linear solver for class scheduling"""

# pylint: skip-file

import datetime

from dateutil.parser import parse as parse_date

from protohaven_api.automation.classes import scheduler as s
from protohaven_api.automation.classes.solver import Class
from protohaven_api.config import tz, tznow
from protohaven_api.testing import d, t


def test_slice_date_range():
    """Slices date range into individual start times"""
    assert s.slice_date_range(t(9, weekday=6), t(14, weekday=6), 3) == [
        t(10, weekday=6)
    ]  # Loose bounds
    assert s.slice_date_range(t(10, weekday=6), t(13, weekday=6), 3) == [
        t(10, weekday=6)
    ]  # Tight bounds still work
    assert not s.slice_date_range(
        t(10, weekday=6), t(12, weekday=6), 3
    )  # Too tight for a 3 hour class
    assert s.slice_date_range(t(9, weekday=0), t(22, weekday=0), 3) == [
        t(18, weekday=0)
    ]  # Only weekday evenings allowed


def test_slice_date_range_tzinfo():
    """Confirm daylight savings is observed for US/Eastern, regardless of incoming time zone info"""
    pre_dst = s.slice_date_range(
        datetime.datetime(year=2024, month=3, day=4, hour=00, tzinfo=tz),
        datetime.datetime(year=2024, month=3, day=5, hour=23, tzinfo=tz),
        3,
    )[0]
    post_dst = s.slice_date_range(
        datetime.datetime(year=2024, month=3, day=12, hour=00, tzinfo=tz),
        datetime.datetime(year=2024, month=3, day=14, hour=23, tzinfo=tz),
        3,
    )[1]
    assert [
        pre_dst.isoformat().rsplit("-")[-1],
        post_dst.isoformat().rsplit("-")[-1],
    ] == ["05:00", "04:00"]


def test_build_instructor_basic():
    """Test that given nominal data, an Instructor is built and returned OK."""
    TEST_CLASS = Class(
        "test_id",
        "Test Class",
        days=1,
        hours=3,
        areas=["a0"],
        exclusions=[[d(5), d(10), d(7)]],
        score=1.0,
    )
    assert s.build_instructor(
        name="testname",
        avail=[[d(1, 18).isoformat(), d(1, 21).isoformat(), "avail_id"]],
        caps=[TEST_CLASS.class_id],
        instructor_occupancy=[],
        area_occupancy={},
        class_by_id={TEST_CLASS.class_id: TEST_CLASS},
    ).avail == [d(1, 18)]


def test_build_instructor_no_class_info():
    """Tests that class info missing doesn't cause breakage"""
    assert (
        s.build_instructor(
            name="testname",
            avail=[[d(1, 18).isoformat(), d(1, 21).isoformat(), "avail_id"]],
            caps=["test_id"],
            instructor_occupancy=[],
            area_occupancy={},
            class_by_id={},
        ).avail
        == []
    )


def test_build_instructor_respects_empty_caps():
    """Capabilities are still listed even when we have no candidate dates"""
    assert s.build_instructor(
        name="testname",
        avail=[],
        caps=["test_cap"],
        instructor_occupancy=[],
        area_occupancy={},
        class_by_id={},
    ).caps == ["test_cap"]


def test_build_instructor_daterange_not_supported():
    """Test that rejected candidates for class/time are returned when the instructor has availability"""
    TEST_CLASS = Class(
        "test_id",
        "Test Class",
        hours=3,
        days=1,
        areas=["a0"],
        exclusions=[[d(5), d(10), d(7)]],
        score=1.0,
    )
    inst = s.build_instructor(
        name="testname",
        avail=[[d(1, 12).isoformat(), d(1, 14).isoformat(), "avail_id"]],
        caps=["test_id"],
        instructor_occupancy=[],
        area_occupancy={},
        class_by_id={TEST_CLASS.class_id: TEST_CLASS},
    )
    assert inst.avail == []
    assert (
        "Available time does not include one of the scheduler's allowed class times"
        in inst.rejected["Availability Validation"][0]["reason"]
    )


def test_build_instructor_no_caps():
    """If instructor has no capabilities, it is mentioned in `rejected`"""
    TEST_CLASS = Class(
        "test_id",
        "Test Class",
        hours=3,
        days=1,
        areas=["a0"],
        exclusions=[[d(5), d(10), d(7)]],
        score=1.0,
    )
    inst = s.build_instructor(
        name="testname",
        avail=[[d(1, 18).isoformat(), d(1, 21).isoformat(), "avail_id"]],
        caps=[],  # <--- no capabilities!
        instructor_occupancy=[],
        area_occupancy={},
        class_by_id={TEST_CLASS.class_id: TEST_CLASS},
    )
    assert inst.avail == []
    assert (
        "Instructor has no capabilities listed"
        in inst.rejected["Instructor Validation"][0]["reason"]
    )


def test_push_schedule(mocker):
    mocker.patch.object(
        s.airtable, "append_classes_to_schedule", return_value=(200, None)
    )
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
                    "Period (from Class)": [30],
                }
            },
            {
                "fields": {
                    "Start Time": "2024-03-01",
                    "Class": ["r1"],
                    "Days (from Class)": [0],
                    "Period (from Class)": [30],
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


def test_load_schedulable_classes(mocker):
    mocker.patch.object(
        s.airtable,
        "get_all_class_templates",
        return_value=[
            {
                "id": "class1",
                "fields": {
                    "Name": "Class One",
                    "Schedulable": True,
                    "Hours": 5,
                    "Days": 2,
                    "Area": ["Area 1"],
                    "Image Link": "http://example.com/image1",
                },
            },
            {
                "id": "class2",
                "fields": {
                    "Name": "Class Two",
                    "Schedulable": True,
                    # Missing "Hours", "Days", "Area"; rejected
                },
            },
            {
                "id": "class3",
                "fields": {
                    "Name": "Class Three",
                    "Schedulable": True,
                    "Hours": 3,
                    "Days": 1,
                    "Area": ["Area 2"],
                    # Missing "Image Link"
                },
            },
        ],
    )
    mocker.patch.object(s, "compute_score", return_value=10)

    classes, notices = s.load_schedulable_classes({})

    assert len(classes) == 2
    assert classes[0].name == "Class One"
    assert classes[1].name == "Class Three"
    assert "missing required fields" in notices["class2"][0]
    assert "Class is missing a promo image" in notices["class3"][0]


def test_generate_env(mocker):
    """Test generate_env function"""
    start_date = d(0)
    end_date = d(1)
    instructor_filter = ["instructor1", "instructor2"]
    include_proposed = True

    mocker.patch.object(
        s.airtable,
        "fetch_instructor_teachable_classes",
        return_value={
            "instructor1": ["class1", "class2"],
            "instructor2": ["class1", "class3"],
        },
    )
    mocker.patch.object(
        s,
        "fetch_formatted_availability",
        return_value={
            "instructor1": [],
            "instructor2": [],
        },
    )
    mocker.patch.object(
        s.airtable,
        "get_class_automation_schedule",
        return_value=[
            {"fields": {"Rejected": None, "Neon ID": "123"}},
            {"fields": {"Rejected": None}},
        ],
    )
    mocker.patch.object(
        s, "gen_class_and_area_stats", return_value=(set(), {}, {"instructor1": []})
    )
    mocker.patch.object(
        s,
        "load_schedulable_classes",
        return_value=(
            [mocker.MagicMock(class_id="class1"), mocker.MagicMock(class_id="class2")],
            [],
        ),
    )

    inst = mocker.MagicMock(
        name="instructor1",
    )
    mocker.patch.object(
        s,
        "build_instructor",
        return_value=inst,
    )

    result = s.generate_env(start_date, end_date, instructor_filter, include_proposed)
    assert result == {
        "area_occupancy": {},
        "classes": [],
        "instructors": [inst.as_dict()],
        "notices": [],
    }
