# pylint: skip-file
import datetime
import json
import re
from collections import namedtuple

import pytest

from protohaven_api.config import safe_parse_datetime, tz
from protohaven_api.integrations import airtable as a
from protohaven_api.integrations import airtable_base as ab
from protohaven_api.testing import d, idfn


def test_set_booked_resource_id(mocker):
    mocker.patch.object(ab, "get_connector")
    ab.get_connector().db_request.return_value = (200, "{}")

    a.set_booked_resource_id("airtable_id", "resource_id")

    fname, args, kwargs = ab.get_connector().db_request.mock_calls[0]
    assert kwargs["data"] == {
        "records": [
            {"id": "airtable_id", "fields": {"BookedResourceId": "resource_id"}}
        ]
    }


Tc = namedtuple("TC", "desc,entries,tag,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("No results OK", [], "foo", {}),
        Tc(
            "Simple match",
            [{"Neon ID": "a", "To": "a@a.com", "Created": d(0).isoformat()}],
            "a",
            {"a@a.com": [d(0)]},
        ),
        Tc(
            "Simple non-match",
            [{"Neon ID": "a", "To": "a@a.com", "Created": d(0).isoformat()}],
            "b",
            {},
        ),
        Tc(
            "Regex match",
            [{"Neon ID": "abcd", "To": "a@a.com", "Created": d(0).isoformat()}],
            re.compile("ab.*"),
            {"a@a.com": [d(0)]},
        ),
        Tc(
            "Regex match on CSV of neon IDs",
            [
                {
                    "Neon ID": "1234,5678,9012",
                    "To": "a@a.com",
                    "Created": d(0).isoformat(),
                }
            ],
            re.compile(".*5678.*"),
            {"a@a.com": [d(0)]},
        ),
    ],
    ids=idfn,
)
def test_get_notifications_after(mocker, tc):
    mocker.patch.object(
        a, "get_all_records_after", return_value=[{"fields": e} for e in tc.entries]
    )
    assert dict(a.get_notifications_after(tc.tag, d(0))) == tc.want


def test_get_reports_for_tool(mocker):
    """Test fetching tool reports for a specific airtable_id"""
    mocker.patch.object(
        a,
        "get_all_records_after",
        return_value=[
            {
                "fields": {
                    "Equipment Record": ["valid_id"],
                    "Created": d(0).strftime("%Y-%m-%d"),
                    "Name": "Test User",
                    "Email": "testuser@example.com",
                    "What's the problem?": "Tool not working",
                    "Actions taken": "Checked settings",
                    "Asana Link": "http://asana.com/task/1",
                    "Current equipment status": "foo",
                }
            },
            {
                "fields": {
                    "Equipment Record": ["nonmatching_id"],
                }
            },
        ],
    )

    reports = list(a.get_reports_for_tool("valid_id"))
    assert len(reports) == 1
    assert reports[0] == {
        "t": d(0),
        "state": "foo",
        "date": d(0).strftime("%Y-%m-%d"),
        "name": "Test User",
        "email": "testuser@example.com",
        "message": "Tool not working",
        "summary": "Checked settings",
        "asana": "http://asana.com/task/1",
    }


Tc = namedtuple("TC", "desc,data,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc(
            "correct role & tool code",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": ["Sandblaster"],
            },
            True,
        ),
        Tc(
            "correct role, non cleared tool code",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": ["Planer"],
            },
            False,
        ),
        Tc(
            "wrong role, cleared tool",
            {
                "Published": "2024-04-01",
                "Roles": ["badrole"],
                "Tool Name (from Tool Codes)": ["Sandblaster"],
            },
            False,
        ),
        Tc(
            "Correct role, no tool",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            True,
        ),
        Tc(
            "too old",
            {
                "Published": "2024-03-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            False,
        ),
        Tc(
            "too new (scheduled)",
            {
                "Published": "2024-05-05",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            False,
        ),
    ],
)
def test_get_announcements_after(mocker, tc):
    """Test announcement fetching"""
    ac = a.AirtableCache()
    ac["announcements"] = [{"fields": tc.data, "id": "123"}]
    mocker.patch.object(a, "tznow", return_value=safe_parse_datetime("2024-04-02"))
    got = list(
        ac.announcements_after(
            safe_parse_datetime("2024-03-14"),
            ["role1"],
            ["SBL: Sandblaster"],
        )
    )
    if tc.want:
        assert got
    else:
        assert not got


def test_get_storage_violations():
    """Test checking member for storage violations"""
    account_id = "123"
    tc = a.AirtableCache()
    tc["violations"] = [
        {"fields": {"Neon ID": account_id, "Violation": "Excessive storage"}},
        {"fields": {"Neon ID": "456", "Closure": "2023-10-01"}},
        {"fields": {"Neon ID": account_id, "Closure": "2023-10-01"}},
    ]

    violations = list(tc.violations_for(account_id))

    assert len(violations) == 1
    assert violations[0]["fields"]["Violation"] == "Excessive storage"
    assert "Closure" not in violations[0]["fields"]


def test_create_coupon(mocker):
    mocker.patch.object(a, "tznow", return_value=d(0))
    mock_insert = mocker.patch.object(a, "insert_records")
    mock_insert.return_value = (200, {"records": [{"id": "rec123"}]})
    result = a.create_coupon(
        "SUMMER25",
        25,
        d(1),
        d(2),
    )
    expected_fields = {
        "Code": "SUMMER25",
        "Amount": 25,
        "Use By": d(1).strftime("%Y-%m-%d"),
        "Created": d(0).isoformat(),
        "Expires": d(2).strftime("%Y-%m-%d"),
    }
    mock_insert.assert_called_once_with(
        [expected_fields], "class_automation", "discounts"
    )


Tc = namedtuple("TC", "desc,records,use_by,expected_count")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("No coupons", [], "2025-01-01", 0),
        Tc(
            "All valid unassigned",
            [{"fields": {"Use By": "2025-02-01", "Assigned": None}}],
            "2025-01-01",
            1,
        ),
        Tc(
            "Some assigned",
            [
                {"fields": {"Use By": "2025-02-01", "Assigned": None}},
                {"fields": {"Use By": "2025-02-01", "Assigned": "2024-01-01"}},
            ],
            "2025-01-01",
            1,
        ),
    ],
    ids=idfn,
)
def test_get_num_valid_unassigned_coupons(mocker, tc):
    mock_get = mocker.patch.object(a, "get_all_records_after")
    mock_get.return_value = tc.records

    count = a.get_num_valid_unassigned_coupons(safe_parse_datetime(tc.use_by))
    assert count == tc.expected_count


Tc = namedtuple("TC", "desc,records,use_by,expected_result")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("No available coupons", [], "2025-01-01", None),
        Tc(
            "Returns first unassigned",
            [
                {"fields": {"Use By": "2025-02-01", "Assigned": None}, "id": "rec1"},
                {"fields": {"Use By": "2025-03-01", "Assigned": None}, "id": "rec2"},
            ],
            "2025-01-01",
            {"id": "rec1", "fields": {"Use By": "2025-02-01", "Assigned": None}},
        ),
        Tc(
            "Skips assigned",
            [
                {
                    "fields": {"Use By": "2025-02-01", "Assigned": "2024-01-01"},
                    "id": "rec1",
                },
                {"fields": {"Use By": "2025-03-01", "Assigned": None}, "id": "rec2"},
            ],
            "2025-01-01",
            {"id": "rec2", "fields": {"Use By": "2025-03-01", "Assigned": None}},
        ),
    ],
    ids=idfn,
)
def test_get_next_available_coupon(mocker, tc):
    mock_get = mocker.patch.object(a, "get_all_records_after")
    mock_get.return_value = tc.records

    result = a.get_next_available_coupon(safe_parse_datetime(tc.use_by))
    assert result == tc.expected_result


def test_mark_coupon_assigned(mocker):
    mock_update = mocker.patch.object(a, "update_record")
    mock_update.return_value = (200, {"id": "rec123"})
    test_time = d(0)  # 2025-01-01
    mocker.patch.object(a, "tznow", return_value=test_time)

    result = a.mark_coupon_assigned("rec123", "user@example.com")

    mock_update.assert_called_once_with(
        {"Assigned": test_time.isoformat(), "Assignee": "user@example.com"},
        "class_automation",
        "discounts",
        "rec123",
    )
    assert result == {"id": "rec123"}


def test_create_fees_batched(mocker):
    """Ensure that create_fees does not overload insert_records' max
    batch size"""
    m = mocker.patch.object(a, "_refid", side_effect=lambda x: x)
    m = mocker.patch.object(a, "insert_records", return_value="ok")
    a.create_fees([["123", 5, 1] for i in range(20)])
    assert len(m.mock_calls) == 2


def test_get_forecast_overrides(mocker):
    """Test getting forecast overrides with and without PII"""
    mock_records = [
        {
            "id": "rec1",
            "fields": {
                "Shift Start": d(0, h=10).isoformat(),
                "Override": "One Tech\nTwo Tech",
                "Last Modified": "2025-01-01",
                "Last Modified By": "Admin",
            },
        },
        {
            "id": "rec2",
            "fields": {
                "Shift Start": d(1, h=16).isoformat(),
                "Override": "Three Tech",
                "Last Modified": "2025-01-02",
                "Last Modified By": "System",
            },
        },
        {
            "id": "rec3",
            "fields": {
                "Shift Start": None,  # Should be skipped
                "Override": "Should Not Appear",
            },
        },
    ]

    mocker.patch.object(a, "get_all_records", return_value=mock_records)

    # Test with PII
    got = list(a.get_forecast_overrides(include_pii=True))
    assert got == [
        ("2025-01-01 AM", ("rec1", ["One Tech", "Two Tech"], "Admin on 2025-01-01")),
        ("2025-01-02 PM", ("rec2", ["Three Tech"], "System on 2025-01-02")),
    ]

    # Test without PII
    got = list(a.get_forecast_overrides(include_pii=False))
    assert got == [
        ("2025-01-01 AM", ("rec1", ["One", "Two"], "2025-01-01")),
        ("2025-01-02 PM", ("rec2", ["Three"], "2025-01-02")),
    ]


def test_fetch_instructor_teachable_classes(mocker):
    """Test fetching teachable classes from airtable"""
    mock_records = [
        {
            "fields": {
                "Neon ID": "12345",
                "Class": ["class1", "class2"],
            }
        },
        {
            "fields": {
                "Neon ID": "67890",
                "Class": ["class3"],
            }
        },
        {"fields": {"Class": ["class5"]}},
    ]

    mocker.patch.object(a, "get_all_records", return_value=mock_records)
    got = a.fetch_instructor_teachable_classes()

    expected = {"12345": ["class1", "class2"], "67890": ["class3"]}
    assert got == expected


def test_insert_quiz_result(mocker):
    """Test inserting quiz result into Airtable"""
    mock_insert = mocker.patch.object(a, "insert_records")
    submitted = d(0)
    email = "test@example.com"
    tool_codes = ["LS1", "LS2"]
    data = {"question": "test", "answer": "correct"}
    points_scored = 8
    points_to_pass = 6

    a.insert_quiz_result(
        submitted, email, tool_codes, data, points_scored, points_to_pass
    )

    mock_insert.assert_called_once_with(
        [
            {
                "Submitted": submitted.isoformat(),
                "Email": email,
                "Tool Codes": "LS1,LS2",
                "Data": '{"question": "test", "answer": "correct"}',
                "Points Scored": points_scored,
                "Points to Pass": points_to_pass,
            }
        ],
        "class_automation",
        "quiz_results",
    )


def test_resolve_hours():
    assert a.Class.resolve_hours(3, 2) == [3, 3]
    assert a.Class.resolve_hours("3", "3") == [3, 3, 3]
    assert a.Class.resolve_hours("3,2,1", None) == [3, 2, 1]
    assert a.Class.resolve_hours(None, None) == [0]


def test_resolve_starts():
    assert a.ScheduledClass.resolve_starts(d(0).isoformat(), None, None, None) == [d(0)]
    assert a.ScheduledClass.resolve_starts(
        f"{d(0).isoformat()}, {d(1).isoformat()}", None, None, None
    ) == [d(0), d(1)]
    assert a.ScheduledClass.resolve_starts(None, d(0).isoformat(), "2", "7") == [
        d(0),
        d(7),
    ]


def test_from_schedule(mocker):
    """Test converting airtable schedule row into ScheduledClass"""
    # Create a mock row with all required fields
    mock_row = {
        "id": "rec123",
        "fields": {
            "Class": ["cls789"],
            "Hours (from Class)": [3],
            "Sessions": f"{d(6, 10).isoformat()},{d(7, 10).isoformat()}",
            "Neon ID": "neon456",
            "Name (from Class)": ["Test Class"],
            "Period (from Class)": [7],
            "Capacity (from Class)": [20],
            "Supply State": "In stock",
            "Name (from Area) (from Class)": ["Woodshop", "Metalshop"],
            "Confirmed": d(0).isoformat(),
            "Rejected": None,
            "Image Link (from Class)": ["https://example.com/image.jpg"],
            "Form Name (from Clearance) (from Class)": ["Safety Training"],
            "Price (from Class)": [100],
            "Email": "instructor@example.com",
            "Instructor": "John Doe",
            "Volunteer": False,
            "Short Description (from Class)": ["A short description"],
            "What you Will Create (from Class)": ["A wooden box"],
            "What to Bring/Wear (from Class)": ["Safety glasses"],
            "Clearances Earned (from Class)": ["Woodshop clearance"],
            "Age Requirement (from Class)": ["18+"],
        },
    }

    result = a.ScheduledClass.from_schedule(mock_row)
    assert result.schedule_id == "rec123"
    assert result.class_id == "cls789"
    assert result.neon_id == "neon456"
    assert result.name == "Test Class"
    assert result.hours == [3, 3]
    assert result.days == 2
    assert result.period == datetime.timedelta(days=7)
    assert result.capacity == 20
    assert result.supply_state == "In stock"
    assert result.areas == ["Woodshop", "Metalshop"]
    assert result.confirmed == d(0)
    assert result.rejected is None
    assert result.image_link == "https://example.com/image.jpg"
    assert result.clearances == ["Safety Training"]
    assert result.price == 100
    assert result.instructor_email == "instructor@example.com"
    assert result.instructor_name == "John Doe"
    assert result.volunteer is False
    expected_sessions = [(d(6, 10), d(6, 13)), (d(7, 10), d(7, 13))]
    assert result.sessions == expected_sessions
    assert result.description == {
        "Short Description": "A short description",
        "What you Will Create": "A wooden box",
        "What to Bring/Wear": "Safety glasses",
        "Clearances Earned": "Woodshop clearance",
        "Age Requirement": "18+",
    }


def test_from_template(mocker):
    """Test converting an airtable template row into Class"""
    row = {
        "id": "rec123",
        "fields": {
            "Name": "Test Class",
            "Hours": "3,3,3",
            "Capacity": "20",
            "Price": "100",
            "Period": "30",
            "Name (from Area)": ["Area1", "Area2"],
            "Schedulable": True,
            "Approved": True,
            "Image Link": "http://example.com/image.jpg",
            "Form Name (from Clearance)": ["TS1"],
            "Email (from Instructor Capabilities)": ["instructor@example.com"],
        },
    }
    result = a.Class.from_template(row)
    assert result.class_id == "rec123"
    assert result.name == "Test Class"
    assert result.hours == [3, 3, 3]
    assert result.capacity == 20
    assert result.price == 100
    assert result.period == datetime.timedelta(days=30)
    assert result.days == 3
    assert result.areas == ["Area1", "Area2"]
    assert result.schedulable is True
    assert result.approved is True
    assert result.image_link == "http://example.com/image.jpg"
    assert result.clearances == ["TS1"]
    assert result.approved_instructors == ["instructor@example.com"]
