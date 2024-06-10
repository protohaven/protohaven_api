# pylint: skip-file
import json

import pytest
from dateutil import parser as dateparser

from protohaven_api.config import tz
from protohaven_api.integrations import airtable as a


def test_set_booked_resource_id(mocker):
    mocker.patch.object(a, "get_connector")
    mocker.patch.object(
        a,
        "cfg",
        return_value={
            "base_id": "test_base_id",
            "token": "test_token",
            "tools": "tools_id",
        },
    )
    a.get_connector().airtable_request.return_value = mocker.MagicMock(content="{}")
    a.set_booked_resource_id("airtable_id", "resource_id")
    fname, args, kwargs = a.get_connector().airtable_request.mock_calls[0]
    assert kwargs["data"] == json.dumps({"fields": {"BookedResourceId": "resource_id"}})
    assert "airtable_id" == kwargs["rec"]


def test_get_all_records(mocker):
    mocker.patch.object(
        a,
        "cfg",
        return_value={
            "base_id": "test_base_id",
            "token": "test_token",
            "test_tbl": "test_tbl_id",
        },
    )
    mocker.patch.object(a, "get_connector")
    a.get_connector().airtable_request.side_effect = [
        mocker.MagicMock(
            status_code=200,
            content=json.dumps({"records": ["foo", "bar", "baz"], "offset": 1}),
        ),
        mocker.MagicMock(
            status_code=200, content=json.dumps({"records": ["fizz", "buzz"]})
        ),
    ]
    assert a.get_all_records("test_base", "test_tbl", suffix="a=test_suffix") == [
        "foo",
        "bar",
        "baz",
        "fizz",
        "buzz",
    ]
    _, args, kwargs = a.get_connector().airtable_request.mock_calls[0]
    print(kwargs)
    assert kwargs["suffix"] == "?offset=&a=test_suffix"

    _, args, kwargs = a.get_connector().airtable_request.mock_calls[1]
    print(kwargs)
    assert kwargs["suffix"] == "?offset=1&a=test_suffix"


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
    ],
)
def test_get_announcements_after(desc, data, want, mocker):
    mocker.patch.object(
        a, "_get_announcements_cached_impl", return_value=[{"fields": data}]
    )
    got = a.get_announcements_after(
        dateparser.parse("2024-03-14").astimezone(tz), ["role1"], ["Sandblaster"]
    )
    if want:
        assert got
    else:
        assert not got
