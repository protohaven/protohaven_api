# pylint: skip-file
import datetime
import json
from collections import namedtuple

import pytest
from dateutil import parser as dateparser

from protohaven_api.config import tz
from protohaven_api.integrations import airtable as a
from protohaven_api.integrations import airtable_base as ab
from protohaven_api.testing import d, idfn


def test_set_booked_resource_id(mocker):
    mocker.patch.object(ab, "get_connector")
    mocker.patch.object(
        ab,
        "cfg",
        return_value={
            "base_id": "test_base_id",
            "token": "test_token",
            "tools": "tools_id",
        },
    )
    ab.get_connector().airtable_request.return_value = (200, "{}")

    a.set_booked_resource_id("airtable_id", "resource_id")

    fname, args, kwargs = ab.get_connector().airtable_request.mock_calls[0]
    assert kwargs["data"] == json.dumps({"fields": {"BookedResourceId": "resource_id"}})
    assert "airtable_id" == kwargs["rec"]


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
def test_get_announcements_after(desc, data, want, mocker):
    mocker.patch.object(
        a,
        "_get_announcements_cached_impl",
        return_value=[{"fields": data, "id": "123"}],
    )
    mocker.patch.object(
        a, "tznow", return_value=dateparser.parse("2024-04-02").astimezone(tz)
    )
    got = list(
        a.get_announcements_after(
            dateparser.parse("2024-03-14").astimezone(tz), ["role1"], ["Sandblaster"]
        )
    )
    if want:
        assert got
    else:
        assert not got


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
    ],
    ids=idfn,
)
def test_expand_instructor_availability(mocker, tc):
    got = list(a.expand_instructor_availability(tc.records, tc.t0, tc.t1))
    assert got == tc.want


# @pytest.mark.parametrize(
#     "desc,rec,cut_start,cut_end,want",
#     [
#         (
#             "Delete",
#             _arec("a", d(0, 18), d(0, 21), 1),
#             None,
#             None,
#             (None, None),
#         ),
#         (
#             "Truncate",
#             _arec("a", d(0, 18), d(0, 21), 1),
#             d(3),
#             None,
#             ({"Interval End": d(3)}, None),
#         ),
#         (
#             "Slice",
#             _arec("a", d(0, 18), d(0, 21), "RRULE:FREQ=DAILY;COUNT=5"),
#             d(2),
#             d(4),
#             (
#                 {"Interval End": d(2)},
#                 _arec("a", d(4, 18), d(4, 21), "RRULE:FREQ=DAILY;COUNT=5"),
#             ),
#         ),
#     ],
# )
# def test_trim_availability(mocker, desc, rec, cut_start, cut_end, want):
#     mocker.patch.object(a, "get_record", return_value=rec)
#     mocker.patch.object(a, "update_record", side_effect=lambda data, _0, _1, _2: data)
#     mocker.patch.object(a, "delete_record", side_effect=lambda _0, _1, _2: None)
#     mocker.patch.object(
#         a,
#         "insert_records",
#         side_effect=lambda data, _0, _1: mocker.MagicMock(
#             content=json.dumps(
#                 {
#                     "records": [
#                         {
#                             "fields": {
#                                 **data[0],
#                                 "Email (from Instructor)": "a",
#                             },  # Indirect field requires override for testing
#                             "id": 123,
#                         }
#                     ]
#                 }
#             )
#         ),
#     )
#     got = a.trim_availability("rec_id", cut_start, cut_end)
#     assert got == want
