# pylint: skip-file
import json

from protohaven_api.integrations.data.dev_neon import handle


def test_get_events_dev():
    rep = handle("https://api.neoncrm.com/v2/events")
    assert rep.status_code == 200
    data = rep.get_json()
    assert isinstance(data["events"], list)
    assert len(data["events"]) > 0


def test_get_event_dev():
    e = handle("/events").get_json()["events"][0]

    got = handle(f"/events/{e['id']}")
    assert got.status_code == 200
    assert got.get_json()["id"] == e["id"]


def test_search_accounts_dev():
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
    rep = handle(
        "/accounts/search",
        "POST",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    assert rep.status_code == 200
    got = rep.get_json()["searchResults"]
    assert len(got) > 0
    print(got)
    assert got[0]["First Name"] == "Test"
