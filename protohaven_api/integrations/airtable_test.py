# pylint: skip-file
import datetime
import json
import re
from collections import namedtuple

import pytest
from dateutil import parser as dateparser

from protohaven_api.config import tz
from protohaven_api.integrations import airtable as a
from protohaven_api.integrations import airtable_base as ab
from protohaven_api.testing import d, idfn


def test_set_booked_resource_id(mocker):
    mocker.patch.object(ab, "get_connector")
    ab.get_connector().airtable_request.return_value = (200, "{}")

    a.set_booked_resource_id("airtable_id", "resource_id")

    fname, args, kwargs = ab.get_connector().airtable_request.mock_calls[0]
    assert kwargs["data"] == json.dumps({"fields": {"BookedResourceId": "resource_id"}})
    assert "airtable_id" == kwargs["rec"]


def _arec(email, start, end, rrule=""):
    return {
        "id": 123,
        "fields": {
            "Instructor": [123],
            "Email (from Instructor)": email,
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
                    dateparser.parse("2024-11-02T18:00").astimezone(tz),
                    dateparser.parse("2024-11-02T21:00").astimezone(tz),
                    "RRULE:FREQ=DAILY",
                )
            ],
            dateparser.parse("2024-11-02").astimezone(tz),
            dateparser.parse("2024-11-04").astimezone(tz),
            [
                (
                    123,
                    dateparser.parse("2024-11-02T18:00").astimezone(tz),
                    dateparser.parse("2024-11-02T21:00").astimezone(tz),
                ),
                (
                    123,
                    dateparser.parse("2024-11-03T18:00").astimezone(tz),
                    dateparser.parse("2024-11-03T21:00").astimezone(tz),
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
        "get_all_records",
        return_value=[
            {
                "fields": {
                    "Equipment Record": ["valid_id"],
                    "Created": "2023-10-01",
                    "Name": "Test User",
                    "Email": "testuser@example.com",
                    "What's the problem?": "Tool not working",
                    "Actions taken": "Checked settings",
                    "Asana Link": "http://asana.com/task/1",
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
        "date": "2023-10-01",
        "name": "Test User",
        "email": "testuser@example.com",
        "message": "Tool not working",
        "summary": "Checked settings",
        "asana": "http://asana.com/task/1",
    }


@pytest.mark.parametrize(
    "desc, data, want",
    [
        (
            "correct role & tool code",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": ["Sandblaster"],
            },
            True,
        ),
        (
            "correct role, non cleared tool code",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": ["Planer"],
            },
            False,
        ),
        (
            "wrong role, cleared tool",
            {
                "Published": "2024-04-01",
                "Roles": ["badrole"],
                "Tool Name (from Tool Codes)": ["Sandblaster"],
            },
            False,
        ),
        (
            "Correct role, no tool",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            True,
        ),
        (
            "too old",
            {
                "Published": "2024-03-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            False,
        ),
        (
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
def test_get_announcements_after(
    desc, data, want, mocker
):  # pylint: disable=unused-argument
    """Test announcement fetching"""
    tc = a.AirtableCache()
    tc["announcements"] = [{"fields": data, "id": "123"}]
    mocker.patch.object(
        a, "tznow", return_value=dateparser.parse("2024-04-02").astimezone(tz)
    )
    got = list(
        tc.announcements_after(
            dateparser.parse("2024-03-14").astimezone(tz),
            ["role1"],
            ["SBL: Sandblaster"],
        )
    )
    if want:
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
