# pylint: skip-file
import json

from protohaven_api.integrations.data import dev_airtable as a


def test_get_records_dev(mocker):
    mocker.patch.object(a, "_base_lookup", return_value="foo")
    mocker.patch.object(a, "_tbl_lookup", return_value="bar")
    mocker.patch.object(
        a, "mock_data", return_value={"airtable": {"foo": {"bar": [1, 2, 3]}}}
    )
    rep = a.handle("GET", "http://domain.xyz/v0/BASE_ID/TBL_ID", None)
    assert rep.status_code == 200
    assert len(json.loads(rep.data)["records"]) == 3
