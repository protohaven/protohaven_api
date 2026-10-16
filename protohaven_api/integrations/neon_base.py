"""Helper methods for the code in integrations.neon"""

import json
import logging
import urllib
from typing import Any

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector
from protohaven_api.integrations.models import Member

log = logging.getLogger("integrations.neon_base")

BASE_URL = get_config("neon/base_url")

NeonID = str


def paginated_fetch(api_key, path, params=None, batching=False):
    """Issue GET requests against Neon's V2 API, yielding all results across
    all result pages"""
    current_page = 0
    total_pages = 1
    result_field = path.split("/")[-1]
    params = params or {}
    while current_page < total_pages:
        params["currentPage"] = current_page
        content = get_connector().neon_request(
            get_config("neon")[api_key],
            "GET",
            urllib.parse.urljoin(BASE_URL, path.lstrip("/"))
            + f"?{urllib.parse.urlencode(params)}",
        )
        if isinstance(content, list):
            raise RuntimeError(f"Got content of type list, expected dict: {content}")
        total_pages = content["pagination"]["totalPages"]
        if content[result_field]:
            if batching:
                yield content[result_field]
            else:
                yield from content[result_field]
        current_page += 1
        log.info(f"paginated_fetch {current_page} / {total_pages} fetched")


def paginated_search(search_fields, output_fields, typ="accounts", pagination=None):
    """Issue POST requests against Neon's V2 API, yielding all results across
    all result pages"""
    cur = 0
    data: dict[str, Any] = {
        "searchFields": [
            {"field": f, "operator": o, "value": v} for f, o, v in search_fields
        ],
        "outputFields": list(
            set(output_fields)
        ),  # Prevent duplicates; causes neon request failure
        "pagination": {"currentPage": cur, "pageSize": 50, **(pagination or {})},
    }
    total = 1
    while cur < total:
        content = get_connector().neon_request(
            get_config("neon/api_key2"),
            "POST",
            urllib.parse.urljoin(BASE_URL, f"{typ}/search"),
            data=json.dumps(data),
            headers={"content-type": "application/json"},
        )
        if content.get("searchResults") is None or content.get("pagination") is None:
            raise RuntimeError(f"Search failed: {content}")

        total = content["pagination"]["totalPages"]
        cur += 1
        data["pagination"]["currentPage"] = cur
        log.info(f"paginated_search {cur} / {total} fetched")
        yield from content["searchResults"]


def fetch_memberships_internal_do_not_call_directly(account_id):
    """Fetch membership history of an account in Neon"""
    return list(paginated_fetch("api_key2", f"/accounts/{account_id}/memberships"))


def fetch_account(account_id, required=False, raw=False, fetch_memberships=False):
    """Fetches account information for a specific user in Neon, as a Member()
    Raises RuntimeError if an error is returned from the server, or None
    if the account is not found.
    """
    content = get("api_key1", f"/accounts/{account_id}")
    if isinstance(content, list):
        raise RuntimeError(content)
    if content is None and required:
        raise RuntimeError(f"Account not found: {account_id}")
    if content is None and not required:
        return None
    if raw:
        return content
    m = Member.from_neon_fetch(content)

    if callable(fetch_memberships):
        fetch_memberships = fetch_memberships(m)

    if fetch_memberships:
        m.set_membership_data(
            fetch_memberships_internal_do_not_call_directly(account_id)
        )
    return m


def get(api_key, path):
    """Send an HTTP GET request"""
    return get_connector().neon_request(
        get_config("neon")[api_key],
        "GET",
        urllib.parse.urljoin(BASE_URL, path.lstrip("/")),
    )


def _req(api_key, path, method, body):
    log.info(f"{api_key} {path} {method}")
    return get_connector().neon_request(
        get_config("neon")[api_key],
        method,
        urllib.parse.urljoin(BASE_URL, path.lstrip("/")),
        data=json.dumps(body),
        headers={"content-type": "application/json"},
    )


def patch(api_key, path, body):
    """Send an HTTP PATCH request"""
    return _req(api_key, path, "PATCH", body)


def put(api_key, path, body):
    """Send an HTTP PUT request"""
    return _req(api_key, path, "PUT", body)


def post(api_key, path, body):
    """Send an HTTP POST request"""
    return _req(api_key, path, "POST", body)


def delete(api_key, path):
    """Send an HTTP DELETE request"""
    return get_connector().neon_request(
        get_config("neon")[api_key],
        "DELETE",
        urllib.parse.urljoin(BASE_URL, path.lstrip("/")),
    )


def patch_account(account_id, data, is_company=None):
    """Patch an existing account via Neon V2 API"""
    if is_company is None:
        acct = fetch_account(account_id, required=True)
        if acct:
            is_company = acct.is_company()
    return patch(
        "api_key2",
        f"/accounts/{account_id}",
        {"companyAccount": data} if is_company else {"individualAccount": data},
    )


def extract_custom_field(acc, field_id):
    """Extracts a custom field's value from a fetched account"""
    field_id = str(field_id)
    for cf in acc.get("accountCustomFields", []):
        if cf["id"] == field_id:
            return cf.get("value") or cf.get("optionValues")
    return []


def set_custom_fields(account_id, *fields, is_company=None):
    """Set any custom field for a user in Neon"""
    return patch_account(
        account_id,
        {
            "accountCustomFields": [
                (
                    {"id": field_id, "optionValues": value}
                    if isinstance(value, list)
                    else {"id": field_id, "value": value}
                )
                for field_id, value in fields
            ]
        },
        is_company,
    )
