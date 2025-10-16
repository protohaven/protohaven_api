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
    assert kwargs["data"] == {"fields": {"BookedResourceId": "resource_id"}}
    assert "airtable_id" == kwargs["rec"]


def _arec(email, start, end, rrule=""):
    return {
        "id": 123,
        "fields": {
            "Instructor": [123],
            "Start": start.isoformat(),
            "End": end.isoformat(),
            "Recurrence": rrule,
        },
    }


Tc = namedtuple("TC", "desc,records,t0,t1,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc(
            "Simple inclusion",
            [_arec("a", d(0, 18), d(0, 21))],
            d(-2),
            d(2),
            [(123, d(0, 18), d(0, 21))],
        ),
        Tc(
            "Daily repeat returns on next day availability",
            [_arec("a", d(0, 18), d(0, 21), "RRULE:FREQ=DAILY")],
            d(1),
            d(2),
            [(123, d(1, 18), d(1, 21))],
        ),
        Tc(
            "No returns if before repeating event",
            [_arec("a", d(0, 18), d(0, 21), "RRULE:FREQ=DAILY")],
            d(-2),
            d(-1),
            [],
        ),
        Tc(
            "Availability is clamped by t0 and t1, no recurrence",
            [_arec("a", d(0, 18), d(0, 21))],
            d(0, 19),
            d(0, 20),
            [(123, d(0, 19), d(0, 20))],
        ),
        Tc(
            "Availability is clamped by t0 and t1, with recurrence",
            [_arec("a", d(0, 18), d(0, 21), "RRULE:FREQ=DAILY")],
            d(0, 19),
            d(0, 20),
            [(123, d(0, 19), d(0, 20))],
        ),
        Tc(
            "2d repetition skips over search window",
            [_arec("a", d(0, 18), d(0, 21), "RRULE:FREQ=DAILY;INTERVAL=2")],
            d(1),
            d(2),
            [],
        ),
        Tc(
            "Long repetition test",
            [_arec("a", d(0, 18), d(0, 21), "RRULE:FREQ=DAILY")],
            d(365),
            d(366),
            [(123, d(365, 18), d(365, 21))],
        ),
        Tc(
            "Multiple returns",
            [_arec("a", d(0, 18), d(0, 21), "RRULE:FREQ=DAILY")],
            d(1),
            d(3),
            [(123, d(1, 18), d(1, 21)), (123, d(2, 18), d(2, 21))],
        ),
        Tc(
            "Search after interval end returns nothing",
            [_arec("a", d(0, 18), d(0, 21), "RRULE:FREQ=DAILY;COUNT=5")],
            d(6),
            d(7),
            [],
        ),
        Tc(
            "Across day boundary with weekly repeat",
            [
                _arec("a", d(0, 21), d(1, 2), "RRULE:FREQ=WEEKLY;BYDAY=WE")
            ],  # d(0) is a wednesday
            d(-2),
            d(10),
            [(123, d(0, 21), d(1, 2)), (123, d(7, 21), d(8, 2))],
        ),
        Tc(
            "RRULE parsing errors are ignored; non-recurrent date used",
            [_arec("a", d(0, 18), d(0, 21), "RRULE:::FREQ==ASDF;;=;=")],
            d(-2),
            d(2),
            [(123, d(0, 18), d(0, 21))],
        ),
        Tc(
            "OK across daylight savings time boundary",  # Boundary at 2024-11-03, 3AM EST
            [
                _arec(
                    "a",
                    safe_parse_datetime("2024-11-02T18:00"),
                    safe_parse_datetime("2024-11-02T21:00"),
                    "RRULE:FREQ=DAILY",
                )
            ],
            safe_parse_datetime("2024-11-02"),
            safe_parse_datetime("2024-11-04"),
            [
                (
                    123,
                    safe_parse_datetime("2024-11-02T18:00"),
                    safe_parse_datetime("2024-11-02T21:00"),
                ),
                (
                    123,
                    safe_parse_datetime("2024-11-03T18:00"),
                    safe_parse_datetime("2024-11-03T21:00"),
                ),
            ],
        ),
    ],
    ids=idfn,
)
def test_expand_instructor_availability(mocker, tc):
    got = list(a.expand_instructor_availability(tc.records, tc.t0, tc.t1))
    assert got == tc.want


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
    test_time = datetime.datetime(2025, 1, 1, tzinfo=tz)
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
                "Instructor": "  John Doe  ",
                "Schedulable": True,
                "Class": ["class1", "class2"],
            }
        },
        {
            "fields": {
                "Instructor": "jane smith",
                "Schedulable": True,
                "Class": ["class3"],
            }
        },
        {
            "fields": {
                "Instructor": "bob wilson",
                "Schedulable": False,
                "Class": ["class4"],
            }
        },
        {"fields": {"Schedulable": True, "Class": ["class5"]}},
    ]

    mocker.patch.object(a, "get_all_records", return_value=mock_records)
    got = a.fetch_instructor_teachable_classes()

    expected = {"john doe": ["class1", "class2"], "jane smith": ["class3"]}
    assert got == expected
