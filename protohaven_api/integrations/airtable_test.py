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
            "Summary (max 140 chars) (from Class)": ["Summary"],
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
    assert result.event_id == "neon456"
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
        "Summary (max 140 chars)": "Summary",
        "Short Description": "A short description",
        "What you Will Create": "A wooden box",
        "What to Bring/Wear": "Safety glasses",
        "Clearances Earned": "Woodshop clearance",
        "Age Requirement": "18+",
    }

    assert result.form_fmt_hours(-1) == "0"
    assert result.form_fmt_hours(0.5) == "0.5"
    assert result.form_fmt_hours(3.0) == "3"
    assert result.form_fmt_hours(3.2) == "3"
    assert result.form_fmt_hours(3.8) == "4"
    assert result.form_fmt_hours(999) == "8"


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
            "Neon ID (from Instructor Capabilities)": ["12345"],
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
    assert result.approved_instructors == ["12345"]


def _scheduled_class():
    """Build a ScheduledClass using the public from_schedule constructor"""
    return a.ScheduledClass.from_schedule(
        {
            "id": "rec123",
            "fields": {
                "Class": ["cls1"],
                "Hours (from Class)": [3],
                "Sessions": d(6, 10).isoformat(),
                "Neon ID": "neon1",
                "Name (from Class)": ["Woodworking Basics"],
                "Period (from Class)": [7],
                "Capacity (from Class)": [6],
                "Supply State": "In stock",
                "Name (from Area) (from Class)": ["Woodshop"],
                "Confirmed": None,
                "Rejected": None,
                "Image Link (from Class)": ["https://img.example/x.jpg"],
                "Form Name (from Clearance) (from Class)": ["SBL", "NonToolClearance"],
                "Price (from Class)": [100],
                "Email": "INSTRUCTOR@example.com",
                "Instructor": "Jane Doe",
                "Volunteer": True,
            },
        }
    )


def test_scheduled_class_end_time_neon_id_as_response(mocker):
    """ScheduledClass derived properties and response formatting"""
    sc = _scheduled_class()
    assert sc.neon_id == "neon1"
    assert sc.end_time == sc.start_time + datetime.timedelta(hours=3)
    mocker.patch.object(a.ScheduledClass, "prefill_form", return_value="http://prefill")
    got = sc.as_response(["a@example.com"])
    assert got["neon_id"] == "neon1"
    assert got["prefill"].startswith("http")
    assert got["period"] == 7.0


def test_prefill_form(mocker):
    """prefill_form builds instructor log URL for tool and non-tool clearances"""
    sc = _scheduled_class()
    mocker.patch.object(a, "get_instructor_log_tool_codes", return_value=("SBL",))
    mocker.patch.object(
        a,
        "get_config",
        side_effect=lambda k: {
            "forms/instructor_log/base_url": "https://forms.example/log",
            "forms/instructor_log/keys": {
                "instructor": "instr",
                "date": "date",
                "hours": "hours",
                "class_name": "class",
                "volunteer": "vol",
                "session_type": "session",
                "pass_emails": "pass",
                "clearance_codes": "cc",
                "tool_usage": "tu",
                "event_id": "evt",
                "tool_codes": "tc",
            },
            "forms/instructor_log/values": {
                "volunteer_yes": "Y",
                "single_session": "S",
                "tool_usage_yes": "TY",
                "tool_usage_no": "TN",
            },
        }[k],
    )
    got = sc.prefill_form(["a@example.com"])
    assert "instr=Jane%20Doe" in got
    assert "date=" + d(6).strftime("%Y-%m-%d") in got
    assert "hours=3" in got
    assert "vol=Y" in got
    assert "cc=NonToolClearance" in got
    assert "tu=TY" in got
    assert "tc=SBL" in got


def test_get_class_automation_schedule_raw(mocker):
    """Raw schedule skips unlinked rows and optionally includes rejected rows"""
    rows = [
        {"fields": {}},
        {"fields": {"Class": ["c1"], "Rejected": "2025-01-01"}},
        {"fields": {"Class": ["c2"]}},
    ]
    mocker.patch.object(a, "get_all_records", return_value=rows)
    assert len(list(a.get_class_automation_schedule_raw())) == 2
    assert len(list(a.get_class_automation_schedule_raw(include_rejected=False))) == 1


def test_get_class_automation_schedule_and_get_scheduled_class(mocker):
    """Schedule rows are converted and single records fetched by ID"""
    mocker.patch.object(
        a, "get_class_automation_schedule_raw", return_value=[{"fields": {}}]
    )
    mocker.patch.object(a.ScheduledClass, "from_schedule", return_value="SC")
    assert list(a.get_class_automation_schedule()) == ["SC"]

    mocker.patch.object(a, "get_record", return_value="row")
    assert a.get_scheduled_class("rec1") == "SC"


def test_get_instructor_neon_id_map(mocker):
    """Instructor maps filter by email, active status, and teachable classes"""
    rows = [
        {
            "fields": {
                "Email": "a@x.com",
                "Neon ID": "1",
                "Active": True,
                "Class": ["c1"],
            }
        },
        {
            "fields": {
                "Email": "b@x.com",
                "Neon ID": "2",
                "Active": False,
                "Class": ["c1"],
            }
        },
        {"fields": {"Email": "c@x.com", "Neon ID": "3", "Active": True}},
        {"fields": {"Email": "d@x.com", "Neon ID": "4", "Active": True, "Class": 3}},
    ]
    mocker.patch.object(a, "get_all_records", return_value=rows)
    assert a.get_instructor_neon_id_map() == {
        "1": "a@x.com",
        "2": "b@x.com",
        "3": "c@x.com",
        "4": "d@x.com",
    }
    assert a.get_instructor_neon_id_map(require_active=True) == {
        "1": "a@x.com",
        "3": "c@x.com",
        "4": "d@x.com",
    }
    assert a.get_instructor_neon_id_map(require_teachable_classes=True) == {
        "1": "a@x.com",
        "2": "b@x.com",
    }


def test_fetch_instructor_capabilities(mocker):
    """Capabilities for one instructor are formatted from the capabilities table"""
    rows = [
        {"fields": {"Neon ID": "999"}},
        {
            "id": "cap1",
            "fields": {
                "Neon ID": "123",
                "W9 Form": "w9",
                "Direct Deposit Info": "dd",
                "Bio": "bio",
                "Class": ["c1", "c2"],
                "Name (from Class)": ["Wood", "Metal"],
                "Profile Pic": [{"url": "https://img.example/p.jpg"}],
            },
        },
    ]
    mocker.patch.object(a, "get_all_records", return_value=rows)
    got = a.fetch_instructor_capabilities("123")
    assert got["id"] == "cap1"
    assert got["classes"] == {"c1": "Wood", "c2": "Metal"}
    assert got["profile_pic"] == "https://img.example/p.jpg"
    assert a.fetch_instructor_capabilities("nope") is None


def test_get_all_class_templates_and_get_class_template(mocker):
    """Raw template iteration and single template lookup"""
    rows = [{"id": "cls1", "fields": {"Name": "Wood"}}]
    mocker.patch.object(a, "get_all_records", return_value=rows)
    mocker.patch.object(a.Class, "from_template", return_value="Class")
    assert list(a.get_all_class_templates()) == [rows[0], "Class"]

    mocker.patch.object(
        a, "get_all_class_templates", return_value=iter([{"id": "cls1", "fields": {}}])
    )
    assert a.get_class_template("cls1") == "Class"
    assert a.get_class_template("nope") is None


def test_append_classes_to_schedule(mocker):
    """Class links are converted to the correct reference format before insert"""
    mocker.patch.object(a, "_refid", side_effect=["ref1", "ref2"])
    insert = mocker.patch.object(a, "insert_records")
    payload = [
        {"Instructor": "Jane", "Email": "j@x", "Sessions": "s", "Class": ["c1", "c2"]}
    ]
    a.append_classes_to_schedule(payload)
    insert.assert_called_once_with(
        [
            {
                "Instructor": "Jane",
                "Email": "j@x",
                "Sessions": "s",
                "Class": ["ref1", "ref2"],
            }
        ],
        "class_automation",
        "schedule",
    )


def test_role_intent_logging(mocker):
    """Role intents are fetched and their notified timestamps updated"""
    mocker.patch.object(a, "get_all_records", return_value=["i1", "i2"])
    assert a.get_role_intents() == ["i1", "i2"]
    mocker.patch.object(a, "tznow", return_value=d(0))
    update = mocker.patch.object(a, "update_record")
    a.log_intents_notified(["i1"])
    update.assert_called_once_with(
        {"Last Notified": d(0).isoformat()}, "people", "automation_intents", "i1"
    )


def test_log_comms_success_and_error(mocker):
    """Comms log insert failures are surfaced"""
    insert = mocker.patch.object(a, "insert_records", return_value=(200, "ok"))
    a.log_comms("n1", "a@x.com", "Subject", "sent")
    insert.assert_called_once()

    insert.return_value = (500, "boom")
    with pytest.raises(RuntimeError, match="boom"):
        a.log_comms("n1", "a@x.com", "Subject", "sent")


def test_get_instructor_log_tool_codes(mocker):
    """Tool codes for instructor log forms are cached as a tuple"""
    a.get_instructor_log_tool_codes.cache_clear()
    mocker.patch.object(
        a, "get_all_records", return_value=[{"fields": {"Form Name": "SBL"}}]
    )
    assert a.get_instructor_log_tool_codes() == ("SBL",)
    a.get_instructor_log_tool_codes.cache_clear()


def test_respond_class_automation_schedule(mocker):
    """Schedule confirm/reject updates the correct field"""
    mocker.patch.object(a, "tznow", return_value=d(0))
    update = mocker.patch.object(a, "update_record", return_value=(200, "ok"))
    get = mocker.patch.object(a, "get_scheduled_class", return_value="SC")
    assert a.respond_class_automation_schedule("rec", True) == "SC"
    assert update.call_args_list[0].args[0] == {
        "Confirmed": d(0).isoformat(),
        "Rejected": "",
    }
    assert a.respond_class_automation_schedule("rec", False) == "SC"
    assert update.call_args_list[1].args[0] == {
        "Confirmed": "",
        "Rejected": d(0).isoformat(),
    }


def test_apply_violation_accrual(mocker):
    """Violation accrual update passes through to Airtable"""
    update = mocker.patch.object(a, "update_record")
    a.apply_violation_accrual("v1", 5)
    update.assert_called_once_with(
        {"Accrued": 5}, "policy_enforcement", "violations", "v1"
    )


def test_mark_schedule_supply_request_and_volunteer(mocker):
    """Supply and volunteer schedule updates return the refreshed class"""
    update = mocker.patch.object(a, "update_record", return_value=(200, "ok"))
    get = mocker.patch.object(a, "get_scheduled_class", return_value="SC")
    assert a.mark_schedule_supply_request("rec", "In stock") == "SC"
    assert a.mark_schedule_volunteer("rec", True) == "SC"
    assert update.call_args_list[0].args[0] == {"Supply State": "In stock"}
    assert update.call_args_list[1].args[0] == {"Volunteer": True}


def test_get_tools_and_areas(mocker):
    """Tool and area records are returned directly"""
    mocker.patch.object(a, "get_all_records", return_value=["tool"])
    assert a.get_tools() == ["tool"]
    mocker.patch.object(a, "get_all_records", return_value=["area"])
    assert a.get_areas() == ["area"]


def test_get_tool_id_and_name(mocker):
    """Tool lookup by code is case-insensitive and returns None for misses"""
    mocker.patch.object(
        a,
        "get_tools",
        return_value=[
            {"id": "rec1", "fields": {"Tool Code": "SBL", "Tool Name": "Sandblaster"}}
        ],
    )
    assert a.get_tool_id_and_name(" sbl ") == ("rec1", "Sandblaster")
    assert a.get_tool_id_and_name("nope") == (None, None)


def test_recert_config_as_dict(mocker):
    """RecertConfig serializes timedeltas and bypass tools for JSON"""
    cfg = a.RecertConfig(
        tool="SBL",
        tool_name="Sandblaster",
        quiz_url="http://quiz",
        expiration=datetime.timedelta(days=30),
        bypass_hours=5,
        bypass_tools={"SBL", "TS1"},
        bypass_cutoff=datetime.timedelta(days=2),
        humanized="30 days",
    )
    got = cfg.as_dict()
    assert got["expiration_sec"] == 30 * 24 * 3600
    assert got["bypass_cutoff_sec"] == 2 * 24 * 3600
    assert set(got["bypass_tools"]) == {"SBL", "TS1"}


def test_get_tool_recert_configs_by_code(mocker):
    """Recert configs skip malformed rows and normalize bypass tools"""
    mocker.patch.object(a, "get_config", return_value="30")
    mocker.patch.object(
        a,
        "get_tools",
        return_value=[
            {"fields": {"Tool Name": "Missing Code"}},
            {"fields": {"Tool Code": "SBL", "Tool Name": "Sandblaster"}},
            {
                "fields": {
                    "Tool Code": "TS1",
                    "Tool Name": "Table Saw",
                    "Recert Quiz": "http://quiz",
                    "Days until Recert Needed": 365,
                    "Reservation Hours to Skip Recert": 5,
                    "Tool Code (from Related Tools for Recert)": ["SBL"],
                    "Recertification": "Annual",
                }
            },
        ],
    )
    got = a.get_tool_recert_configs_by_code()
    assert set(got) == {"TS1"}
    assert got["TS1"].tool_name == "Table Saw"
    assert got["TS1"].expiration == datetime.timedelta(days=365)
    assert got["TS1"].bypass_tools == {"TS1", "SBL"}


def test_get_pending_recertifications(mocker):
    """Pending recerts parse deadlines and optional notification timestamp"""
    mocker.patch.object(
        a,
        "get_all_records",
        return_value=[
            {"fields": {"Neon ID": "1"}},
            {
                "id": "rec1",
                "fields": {
                    "Neon ID": "123",
                    "Tool Code": " SBL ",
                    "Instruction Deadline": "2025-01-02",
                    "Reservation Deadline": "2025-02-02",
                    "Notified": "2025-01-03",
                    "Suspended": True,
                },
            },
        ],
    )
    got = list(a.get_pending_recertifications())
    assert len(got) == 1
    assert got[0].neon_id == "123"
    assert got[0].tool_code == "SBL"
    assert got[0].suspended is True
    assert got[0].notified is not None


def test_insert_and_update_pending_recertification(mocker):
    """Recert insert formats dates; update only includes supplied fields"""
    insert = mocker.patch.object(a, "insert_records")
    a.insert_pending_recertification("123", "SBL", d(0), d(1))
    assert insert.call_args.args[0][0]["Instruction Deadline"] == d(0).strftime(
        "%Y-%m-%d"
    )

    update = mocker.patch.object(a, "update_record", return_value=(200, "ok"))
    assert a.update_pending_recertification("rec", d(0), d(1), True) == "ok"
    assert update.call_args_list[0].args[0] == {
        "Instruction Deadline": d(0).strftime("%Y-%m-%d"),
        "Reservation Deadline": d(1).strftime("%Y-%m-%d"),
        "Suspended": True,
    }
    a.update_pending_recertification("rec")
    assert update.call_args_list[1].args[0] == {}


def test_remove_pending_recertification_and_log_notified(mocker):
    """Recert delete passes through and notifications update timestamps"""
    delete = mocker.patch.object(a, "delete_record")
    a.remove_pending_recertification("rec")
    delete.assert_called_once_with("people", "recertification", "rec")

    mocker.patch.object(a, "tznow", return_value=d(0))
    update = mocker.patch.object(a, "update_record")
    a.log_recerts_notified(["r1", "r2"])
    assert update.call_count == 2


def test_get_signins_between(mocker):
    """Sign-ins use after-query when end is omitted and between-query otherwise"""
    mocker.patch.object(a.SignInEvent, "from_airtable", side_effect=lambda r: r)
    after = mocker.patch.object(a, "get_all_records_after", return_value=["after"])
    between = mocker.patch.object(
        a, "get_all_records_between", return_value=["between"]
    )
    assert list(a.get_signins_between(d(0), None)) == ["after"]
    assert list(a.get_signins_between(d(0), d(1))) == ["between"]
    after.assert_called_once_with("people", "sign_ins", d(0))
    between.assert_called_once_with("people", "sign_ins", d(0), d(1))


def test_insert_signin_and_survey_response(mocker):
    """Sign-in and survey inserts are passed through"""
    insert = mocker.patch.object(a, "insert_records")
    a.insert_signin({"Email": "a@x.com"})
    a.insert_simple_survey_response("ann", "a@x.com", "123", "Yes")
    assert insert.call_count == 2
    assert insert.call_args_list[1].args[0][0]["Response"] == "Yes"


def test_get_all_announcements_and_tech_bios(mocker):
    """Announcement and tech bio records are returned as lists"""
    mocker.patch.object(a, "get_all_records", return_value=["ann"])
    assert a.get_all_announcements() == ["ann"]
    mocker.patch.object(a, "get_all_records", return_value=["bio"])
    assert a.get_all_tech_bios() == ["bio"]


def test_policy_sections_violations_and_fees(mocker):
    """Policy record getters filter records missing required fields"""
    mocker.patch.object(a, "get_all_records", return_value=["sec"])
    assert a.get_policy_sections() == ["sec"]
    mocker.patch.object(
        a,
        "get_all_records",
        return_value=[{"fields": {"Onset": "x"}}, {"fields": {}}],
    )
    assert len(a.get_policy_violations()) == 1
    mocker.patch.object(
        a,
        "get_all_records",
        return_value=[{"fields": {"Created": "x"}}, {"fields": {}}],
    )
    assert len(a.get_policy_fees()) == 1


def test_open_violation(mocker):
    """Opening a violation links section record IDs and sets the correct fields"""
    mocker.patch.object(a, "_refid", return_value="ref1")
    insert = mocker.patch.object(a, "insert_records")
    a.open_violation(
        "rep",
        "123",
        ["sec1"],
        [],
        d(0),
        10,
        "notes",
        tag_number=4,
    )
    fields = insert.call_args.args[0][0]
    assert fields["Relevant Sections"] == ["ref1"]
    assert fields["Neon ID"] == 123
    assert fields["Tag Number"] == 4
    assert fields["Daily Fee"] == 10
    assert insert.call_args.args[1:] == ("policy_enforcement", "violations")


def test_close_violation(mocker):
    """Closing a violation creates a closure record linked to the violation"""
    mocker.patch.object(a, "_refid", return_value="ref1")
    insert = mocker.patch.object(a, "insert_records")
    a.close_violation("v1", "closer", d(0), "notes", fees_outstanding=True)
    fields = insert.call_args.args[0][0]
    assert fields["Violation"] == ["ref1"]
    assert fields["Closer"] == "closer"
    assert fields["Close date"] == "2025-01-01"
    assert fields["Fees outstanding?"] is True
    assert insert.call_args.args[1:] == ("policy_enforcement", "closures")


def test_pay_fee_not_implemented():
    """Fee payment is not implemented"""
    with pytest.raises(NotImplementedError):
        a.pay_fee("f1")


def test_delete_forecast_override(mocker):
    """Forecast override delete returns content"""
    delete = mocker.patch.object(a, "delete_record", return_value=(200, "ok"))
    assert a.delete_forecast_override("rec") == "ok"
    delete.assert_called_once_with("people", "shop_tech_forecast_overrides", "rec")


def test_set_forecast_override(mocker):
    """Forecast overrides are stored as add/remove deltas"""
    mocker.patch.object(a, "safe_parse_datetime", return_value=d(0))
    insert = mocker.patch.object(a, "insert_records", return_value=(200, None))
    update = mocker.patch.object(a, "update_record", return_value=(200, None))
    delete = mocker.patch.object(a, "delete_record", return_value=(200, None))

    # No delta and no record: no-op
    assert a.set_forecast_override(
        None, "2025-01-01", "AM", ["A"], ["A"], "e", "n"
    ) == (200, None)
    insert.assert_not_called()

    # Addition creates a new record
    a.set_forecast_override(None, "2025-01-01", "AM", ["A", "B"], ["A"], "e", "n")
    assert insert.call_args.args[0][0]["Override"] == "+B"

    # Removal updates an existing record
    a.set_forecast_override("rec", "2025-01-01", "AM", ["A"], ["A", "B"], "e", "n")
    assert update.call_args.args[0]["Override"] == "-B"

    # No delta with an existing record deletes it
    a.set_forecast_override("rec", "2025-01-01", "AM", ["A"], ["A"], "e", "n")
    delete.assert_called_once_with("people", "shop_tech_forecast_overrides", "rec")


def test_get_latest_passing_quizzes_by_email_and_tool(mocker):
    """Only passing quizzes after the cutoff are returned, keyed by email/tool"""
    rows = [
        {
            "fields": {
                "Points Scored": 5,
                "Points to Pass": 10,
                "Submitted": d(2).isoformat(),
                "Email": "A@X.com",
                "Tool Codes": "SBL",
            }
        },
        {
            "fields": {
                "Points Scored": 8,
                "Points to Pass": 7,
                "Submitted": d(2).isoformat(),
                "Email": "A@X.com",
                "Tool Codes": "SBL,TS1",
            }
        },
        {
            "fields": {
                "Points Scored": 9,
                "Points to Pass": 7,
                "Submitted": d(1).isoformat(),
                "Email": "A@X.com",
                "Tool Codes": "SBL",
            }
        },
        {
            "fields": {
                "Points Scored": 9,
                "Points to Pass": 7,
                "Submitted": d(0).isoformat(),
                "Email": "A@X.com",
                "Tool Codes": "SBL",
            }
        },
    ]
    mocker.patch.object(a, "get_all_records", return_value=rows)
    got = a.get_latest_passing_quizzes_by_email_and_tool(after=d(1))
    assert got[("a@x.com", "SBL")] == d(2)
    assert got[("a@x.com", "TS1")] == d(2)
    assert ("a@x.com", "SBL") in got


def test_get_storage_agreements(mocker):
    """Storage agreements parse their start and end dates"""
    mocker.patch.object(
        a,
        "get_all_records",
        return_value=[
            {
                "id": "s1",
                "fields": {
                    "Start Date": d(0).isoformat(),
                    "End Date": d(10).isoformat(),
                    "Note": "n",
                },
            }
        ],
    )
    got = list(a.get_storage_agreements())
    assert got[0]["id"] == "s1"
    assert got[0]["Start Date"] == d(0)
    assert got[0]["End Date"] == d(10)


def test_airtable_cache_refresh(mocker):
    """Cache refresh loads announcements and violations"""
    mocker.patch.object(a, "get_all_announcements", return_value=["ann"])
    mocker.patch.object(a, "get_policy_violations", return_value=["violation"])
    cache = a.AirtableCache()
    cache.refresh()
    assert cache["announcements"] == ["ann"]
    assert cache["violations"] == ["violation"]


def test_get_all_instructor_capabilities_formatted(mocker):
    """Instructor capabilities are formatted for API responses"""
    mocker.patch.object(a, "get_config", return_value="http://nocodb")
    mocker.patch.object(
        a,
        "get_all_records",
        return_value=[
            {
                "id": "inst1",
                "fields": {
                    "Instructor": "Jane",
                    "Email": "j@x.com",
                    "Neon ID": "123",
                    "Active": True,
                    "W9 Form": "w9",
                    "Direct Deposit Info": "dd",
                    "Bio": "bio",
                    "Profile Pic": [{"path": "p.jpg"}],
                    "Class": ["c1"],
                    "Name (from Class)": ["Wood"],
                    "Clearances": ["SBL"],
                    "Discord User": "jane",
                    "Notes": "note",
                },
            }
        ],
    )
    got = a.get_all_instructor_capabilities_formatted()
    assert got[0]["id"] == "inst1"
    assert got[0]["profile_pic"] == "http://nocodb/p.jpg"
    assert got[0]["classes"] == {"c1": "Wood"}
