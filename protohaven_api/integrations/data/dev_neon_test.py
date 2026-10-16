# pylint: skip-file
import json

from protohaven_api.integrations.data import dev_neon as n


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
