# pylint: skip-file
import json

from protohaven_api.integrations.data import dev_neon as n


def test_get_events_dev(mocker):
    mocker.patch.object(
        n.airtable_base,
        "get_all_records",
        return_value=[
            {"fields": {"eventId": 1, "data": "a"}},
            {"fields": {"eventId": 2, "data": "b"}},
            {"fields": {"eventId": 3, "data": "c"}},
        ],
    )
    rep = n.handle("GET", "https://api.neoncrm.com/v2/events")
    assert rep.status_code == 200
    data = rep.get_json()
    assert isinstance(data["events"], list)
    assert len(data["events"]) > 0


def test_get_event_dev(mocker):
    mocker.patch.object(
        n.airtable_base,
        "get_all_records",
        return_value=[
            {"fields": f}
            for f in (
                {"eventId": 1, "data": {"id": 1}},
                {"eventId": 2, "data": {"id": 2}},
                {"eventId": 3, "data": {"id": 3}},
            )
        ],
    )
    e = n.handle("GET", "/v2/events").get_json()["events"][0]
    got = n.handle("GET", f"/v2/events/{e['id']}")
    assert got.status_code == 200
    assert got.get_json()["id"] == e["id"]


def test_search_accounts_dev(mocker):
    data = {
        "searchFields": [
            {
                "field": "First Name",
                "operator": "EQUAL",
                "value": "Test",
            },
        ],
        "outputFields": [
            "Account ID",
            "First Name",
        ],
        "pagination": {
            "currentPage": 0,
            "pageSize": 1,
        },
    }
    # Matches _paginated_account_search in integrations.neon
    mocker.patch.object(
        n.airtable_base,
        "get_all_records",
        return_value=[
            {
                "fields": {
                    "data": {
                        "individualAccount": {
                            "accountId": 123,
                            "primaryContact": {"firstName": "Test"},
                        }
                    }
                }
            }
        ],
    )
    rep = n.handle(
        "POST",
        "/v2/accounts/search",
        data=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    assert rep.status_code == 200
    got = rep.get_json()["searchResults"]
    assert len(got) > 0
    print(got)
    assert got[0]["First Name"] == "Test"
