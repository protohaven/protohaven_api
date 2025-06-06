"""Test operation of linear solver for class scheduling"""

# pylint: skip-file

import datetime

from dateutil.parser import parse as parse_date

from protohaven_api.automation.classes import scheduler as s
from protohaven_api.automation.classes.solver import Class
from protohaven_api.config import tz, tznow
from protohaven_api.testing import MatchStr, d, t


def test_slice_date_range():
    """Slices date range into individual start times"""
    SUNDAY = 6
    MONDAY = 0

    assert s.slice_date_range(t(9, weekday=SUNDAY), t(14, weekday=SUNDAY), 3) == [
        t(10, weekday=SUNDAY)
    ]  # Loose bounds
    assert s.slice_date_range(t(10, weekday=SUNDAY), t(13, weekday=SUNDAY), 3) == [
        t(10, weekday=SUNDAY)
    ]  # Tight bounds still work
    assert not s.slice_date_range(
        t(10, weekday=SUNDAY), t(12, weekday=SUNDAY), 3
    )  # Too tight for a 3 hour class
    assert s.slice_date_range(t(9, weekday=MONDAY), t(22, weekday=MONDAY), 3) == [
        t(18, weekday=MONDAY)
    ]  # Only weekday evenings allowed
    assert s.slice_date_range(t(9, weekday=SUNDAY), t(16, weekday=SUNDAY), 6) == [
        t(10, weekday=SUNDAY)
    ]  # 5hr class starts at 10am


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
        exclusions=[[d(5), d(10), d(7), "class"]],
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


def test_build_instructor_exclusion():
    """Test that exclusions resrict instructor availability"""
    TEST_CLASS = Class(
        "test_id",
        "Test Class",
        days=1,
        hours=3,
        areas=["a0"],
        exclusions=[[d(5), d(10), d(7), "class"]],
        score=1.0,
    )
    got = s.build_instructor(
        name="testname",
        avail=[[d(6, 18).isoformat(), d(6, 21).isoformat(), "avail_id"]],
        caps=[TEST_CLASS.class_id],
        instructor_occupancy=[],
        area_occupancy={},
        class_by_id={TEST_CLASS.class_id: TEST_CLASS},
    )

    assert got.avail == []
    assert got.rejected["test_id"] == [
        {
            "time": d(6, 18).isoformat(),
            "reason": MatchStr("Too soon before/after same class"),
        }
    ]


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


def test_gen_class_and_area_stats_exclusions(mocker):
    """Verify that exclusions account for the time before and after a run of a class
    that should be avoided when schedling new classes"""
    mocker.patch.object(s, "get_config", return_value=7)
    exclusions, _, clearance_exclusions, _ = s.gen_class_and_area_stats(
        [
            {
                "fields": {
                    "Start Time": "2024-04-01",
                    "Class": ["r1"],
                    "Clearance (from Class)": [12345],
                    "Days (from Class)": [1],
                    "Hours (from Class)": [3],
                    "Period (from Class)": [30],
                    "Name (from Class)": "Class1",
                    "Name (from Area) (from Class)": "Area1",
                    "Instructor": "Foo",
                }
            },
            {
                "fields": {
                    "Start Time": "2024-03-01",
                    "Class": ["r1"],
                    "Clearance (from Class)": [12345],
                    "Days (from Class)": [
                        2
                    ],  # End of exclusion should be from last session
                    "Hours (from Class)": [3],
                    "Period (from Class)": [30],
                    "Name (from Class)": "Class1",
                    "Name (from Area) (from Class)": "Area1",
                    "Instructor": "Foo",
                }
            },
        ],
        parse_date("2024-02-01T00:00:00-04:00"),
        parse_date("2024-05-01T00:00:00-05:00"),
        {12345: "C1"},
        {},
    )
    assert [tuple([d.strftime("%Y-%m-%d") for d in dd]) for dd in exclusions["r1"]] == [
        ("2024-03-02", "2024-05-01", "2024-04-01"),
        ("2024-01-31", "2024-04-07", "2024-03-01"),
    ]
    assert [
        tuple([d.strftime("%Y-%m-%d") for d in dd]) for dd in clearance_exclusions["C1"]
    ] == [
        ("2024-03-25", "2024-04-08", "2024-04-01"),
        ("2024-02-23", "2024-03-08", "2024-03-01"),
    ]


def test_fetch_formatted_availability(mocker):
    mocker.patch.object(
        s.airtable,
        "get_instructor_availability",
        return_value=[
            {
                "id": "rowid",
                "fields": {
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
                    "Name (from Area)": ["Area 1"],
                    "Clearance": ["C1", "C2"],
                    "Image Link": "http://example.com/image1",
                },
            },
            {
                "id": "class2",
                "fields": {
                    "Name": "Class Two",
                    "Schedulable": True,
                    # Missing "Hours", "Days", "Name (from Area)"; rejected
                },
            },
            {
                "id": "class3",
                "fields": {
                    "Name": "Class Three",
                    "Schedulable": True,
                    "Hours": 3,
                    "Days": 1,
                    "Name (from Area)": ["Area 2"],
                    # Missing "Image Link"
                },
            },
        ],
    )
    mocker.patch.object(s, "compute_score", return_value=10)

    classes, notices = s.load_schedulable_classes(
        {"class1": [[d(0), d(2), d(1)]]}, {"C1": [[d(0), d(2), d(1)]]}
    )

    assert notices == {
        "class2": [MatchStr("missing required fields")],
        "class3": [MatchStr("missing a promo image")],
    }
    assert len(classes) == 2
    assert classes[0].name == "Class One"
    assert classes[1].name == "Class Three"
    assert classes[0].exclusions == [
        [d(0), d(2), d(1), "class"],
        [d(0), d(2), d(1), "clearance (C1)"],
    ]


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
    mocker.patch.object(s, "get_reserved_area_occupancy", return_value={})
    mocker.patch.object(
        s.airtable,
        "get_all_records",
        return_value=[
            {"id": "rec1", "fields": {"Code": "Code1"}},
        ],
    )
    mocker.patch.object(
        s, "gen_class_and_area_stats", return_value=(set(), {}, {}, {"instructor1": []})
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
    m1 = mocker.patch.object(s, "build_instructor")

    result = s.generate_env(start_date, end_date, instructor_filter, include_proposed)
    m1.assert_has_calls(
        [
            mocker.call("instructor1", [], ["class1", "class2"], [], {}, mocker.ANY),
            mocker.call("instructor2", [], ["class1", "class3"], [], {}, mocker.ANY),
        ]
    )
    assert len(result["instructors"]) == 2


def test_get_reserved_area_occupancy(mocker):
    """Test that reservations are correctly grouped by area"""
    mock_records = [
        {"fields": {"BookedResourceId": "123", "Name (from Shop Area)": ["Laser"]}},
        {"fields": {"BookedResourceId": "456", "Name (from Shop Area)": ["Wood"]}},
    ]
    mock_reservations = {
        "reservations": [
            {
                "resourceId": "123",
                "bufferedStartDate": d(0, 16).isoformat(),
                "bufferedEndDate": d(0, 19).isoformat(),
                "resourceName": "Laser Cutter",
                "firstName": "Test",
                "lastName": "User",
                "referenceNumber": 789,
            }
        ]
    }

    mocker.patch.object(s, "get_all_records", return_value=mock_records)
    mocker.patch.object(s.booked, "get_reservations", return_value=mock_reservations)

    got = s.get_reserved_area_occupancy(d(0), d(1))

    assert "Laser" in got
    assert len(got["Laser"]) == 1
    assert got["Laser"][0][2] == (
        "Laser Cutter reservation by Test User, "
        "https://reserve.protohaven.org/Web/reservation/?rn=789"
    )
    assert "Wood" not in got
