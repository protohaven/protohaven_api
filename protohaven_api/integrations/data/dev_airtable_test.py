import json

from protohaven_api.integrations.data.dev_airtable import handle


def test_get_records_dev():
    rep = handle("GET", "tools_and_equipment", "tools", None, None, None)
    assert rep.status_code == 200
    assert len(json.loads(rep.content)["records"]) > 0
