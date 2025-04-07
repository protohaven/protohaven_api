# pylint: skip-file
import json

from protohaven_api.integrations import airtable_base as a


def test_get_all_records_airtable(mocker):
    mocker.patch.object(a, "get_connector")
    a.get_connector().db_format.return_value = "airtable"
    a.get_connector().db_request.side_effect = [
        (200, {"records": ["foo", "bar", "baz"], "offset": 1}),
        (200, {"records": ["fizz", "buzz"]}),
    ]
    assert a.get_all_records("test_base", "test_tbl", suffix="a=test_suffix") == [
        "foo",
        "bar",
        "baz",
        "fizz",
        "buzz",
    ]
    _, args, kwargs = a.get_connector().db_request.mock_calls[0]
    assert kwargs["suffix"] == "?offset=&a=test_suffix"

    _, args, kwargs = a.get_connector().db_request.mock_calls[1]
    assert kwargs["suffix"] == "?offset=1&a=test_suffix"


def test_get_all_records_nocodb(mocker):
    mocker.patch.object(a, "get_connector")
    a.get_connector().db_format.return_value = "nocodb"
    rec = {"Id": "id1", "a": 5}
    a.get_connector().db_request.side_effect = [
        (
            200,
            {
                "list": [rec],
                "pageInfo": {"isLastPage": False, "page": 1, "pageSize": 5},
            },
        ),
        (
            200,
            {
                "list": [],
                "pageInfo": {
                    "isLastPage": True,
                },
            },
        ),
    ]
    assert a.get_all_records("test_base", "test_tbl", suffix="a=test_suffix") == [
        {"id": rec["Id"], "fields": rec}
    ]
    _, args, kwargs = a.get_connector().db_request.mock_calls[0]
    print(kwargs)
    assert kwargs["suffix"] == "?offset=&a=test_suffix"

    _, args, kwargs = a.get_connector().db_request.mock_calls[1]
    print(kwargs)
    assert kwargs["suffix"] == "?offset=5&a=test_suffix"
