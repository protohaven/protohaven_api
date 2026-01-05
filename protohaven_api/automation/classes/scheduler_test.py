"""Test operation of linear solver for class scheduling"""

# pylint: skip-file

import datetime

from protohaven_api.automation.classes import scheduler as s
from protohaven_api.config import safe_parse_datetime, tz, tznow
from protohaven_api.testing import MatchStr, d, t


def test_push_class_to_schedule(mocker):
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
    s.push_class_to_schedule(
        "a@b.com", "20", [(d(0, 15), d(0, 18)), (d(1, 15), d(1, 18))]
    )
    s.airtable.append_classes_to_schedule.assert_called_with(
        [
            {
                "Instructor": "test instructor",
                "Email": "a@b.com",
                "Sessions": f"{d(0,15).isoformat()},{d(1,15).isoformat()}",
                "Class": ["20"],
                "Confirmed": now.isoformat(),
            }
        ]
    )


def test_gen_class_and_area_stats_exclusions(mocker):
    """Verify that exclusions account for the time before and after a run of a class
    that should be avoided when schedling new classes"""
    mocker.patch.object(s, "get_config", return_value=7)  # Exclusion range in days
    mocker.patch.object(
        s.airtable,
        "get_class_automation_schedule",
        return_value=[
            mocker.MagicMock(
                sessions=[(d(60, 18), d(60, 21))],
                class_id="r1",
                clearances=["C1"],
                hours=3,
                period=datetime.timedelta(days=30),
                name="Class1",
                areas=["Area1"],
                instructor_name="Foo",
            ),
            mocker.MagicMock(
                sessions=[(d(30, 18), d(30, 21))],
                class_id="r1",
                clearances=["C1"],
                hours=3,
                period=datetime.timedelta(days=30),
                name="Class1",
                areas=["Area1"],
                instructor_name="Foo",
            ),
        ],
    )
    mocker.patch.object(
        s,
        "get_reserved_area_occupancy",
        return_value={
            "Area1": [(d(4), d(6), d(5), "member reserved")],
        },
    )
    env = s.gen_class_and_area_stats(d(20), d(70))
    assert [
        tuple([d.strftime("%Y-%m-%d") for d in (dd.start, dd.end, dd.main_date)])
        for dd in env.exclusions["r1"]
    ] == [
        ("2025-01-31", "2025-04-01", "2025-03-02"),
        ("2025-01-01", "2025-03-02", "2025-01-31"),
    ]
    assert [
        tuple([d.strftime("%Y-%m-%d") for d in (dd.start, dd.end, dd.main_date)])
        for dd in env.clearance_exclusions["C1"]
    ] == [
        ("2025-02-23", "2025-03-09", "2025-03-02"),
        ("2025-01-24", "2025-02-07", "2025-01-31"),
    ]


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
