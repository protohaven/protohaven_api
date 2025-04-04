# pylint: skip-file
import json

from protohaven_api.integrations import airtable_base as a


def test_get_all_records(mocker):
    mocker.patch.object(a, "get_connector")
    a.get_connector().db_request.side_effect = [
        (200, json.dumps({"records": ["foo", "bar", "baz"], "offset": 1})),
        (200, json.dumps({"records": ["fizz", "buzz"]})),
    ]
    assert a.get_all_records("test_base", "test_tbl", suffix="a=test_suffix") == [
        "foo",
        "bar",
        "baz",
        "fizz",
        "buzz",
    ]
    _, args, kwargs = a.get_connector().db_request.mock_calls[0]
    print(kwargs)
    assert kwargs["suffix"] == "?offset=&a=test_suffix"

    _, args, kwargs = a.get_connector().db_request.mock_calls[1]
    print(kwargs)
    assert kwargs["suffix"] == "?offset=1&a=test_suffix"
