# pylint: skip-file
import json

from protohaven_api.integrations import airtable_base as a
from protohaven_api.testing import d


def test_get_all_records_airtable(mocker):
    mocker.patch.object(a, "get_connector")
    a.get_connector().db_format.return_value = "airtable"
    a.get_connector().db_request.side_effect = [
        (200, {"records": ["foo", "bar", "baz"], "offset": 1}),
        (200, {"records": ["fizz", "buzz"]}),
    ]
    assert a.get_all_records("test_base", "test_tbl", {"a": "test_param"}) == [
        "foo",
        "bar",
        "baz",
        "fizz",
        "buzz",
    ]
    _, args, kwargs = a.get_connector().db_request.mock_calls[0]
    assert kwargs["params"]["a"] == "test_param"

    _, args, kwargs = a.get_connector().db_request.mock_calls[1]
    assert kwargs["params"]["a"] == "test_param"


def test_get_all_records_between_airtable(mocker):
    mocker.patch.object(a, "get_connector")
    a.get_connector().db_format.return_value = "airtable"
    a.get_connector().db_request.side_effect = [
        (200, {"records": ["foo", "bar", "baz"]}),
    ]
    assert a.get_all_records_between("test_base", "test_tbl", d(0), d(1)) == [
        "foo",
        "bar",
        "baz",
    ]
    _, args, kwargs = a.get_connector().db_request.mock_calls[0]
    assert d(0).isoformat() in kwargs["params"]["filterByFormula"]
    assert d(1).isoformat() in kwargs["params"]["filterByFormula"]


def test_get_all_records_nocodb(mocker):
    mocker.patch.object(a, "get_connector")
    a.get_connector().db_format.return_value = "nocodb"
    rec = {"id": "id1", "fields": {"a": 5}}
    a.get_connector().db_request.side_effect = [
        (
            200,
            {
                "records": [rec],
                "next": "?page=1&pageSize=5",
            },
        ),
        (
            200,
            {
                "records": [],
            },
        ),
    ]
    assert a.get_all_records("test_base", "test_tbl", params={"a": "test_param"}) == [
        rec
    ]
    _, args, kwargs = a.get_connector().db_request.mock_calls[0]
    print(kwargs)
    assert kwargs["params"]["a"] == "test_param"

    _, args, kwargs = a.get_connector().db_request.mock_calls[1]
    print(kwargs)
    assert kwargs["params"]["a"] == "test_param"


def test_get_all_records_between_nocodb(mocker):
    mocker.patch.object(a, "get_connector")
    a.get_connector().db_format.return_value = "nocodb"
    rec = {"id": "id1", "fields": {"a": 5}}
    a.get_connector().db_request.side_effect = [
        (
            200,
            {
                "records": [rec],
            },
        ),
    ]
    assert a.get_all_records_between("test_base", "test_tbl", d(0), d(1)) == [rec]
    _, args, kwargs = a.get_connector().db_request.mock_calls[0]
    assert d(0).isoformat() in kwargs["params"]["where"]
    assert d(1).isoformat() in kwargs["params"]["where"]
