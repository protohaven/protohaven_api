"""A mock version of Neon CRM serving results pulled from Nocodb"""

import json
import logging
from urllib.parse import urlparse

from flask import Flask, Response, request

from protohaven_api.integrations import airtable_base
from protohaven_api.integrations.data.neon import CustomField

app = Flask(__file__)

log = logging.getLogger("integrations.data.dev_neon")


def first(*args):
    """Return the first non-None field in the sequence"""
    d = args[0]
    for k in args[1:]:
        v = d.get(k)
        if v is not None:
            return v
    return None


def _neon_dev_outputify(rec, field):
    """Output account search formatted info from a canned record"""
    acc = first(rec, "individualAccount", "companyAccount")
    if isinstance(field, int) or field.isdigit():  # Custom fields have integer ids
        cf = [f for f in acc["accountCustomFields"] if str(f["id"]) == str(field)]
        if len(cf) == 0:
            return None
        if cf[0].get("value") is not None:
            return cf[0]["value"]
        v = "|".join([v["name"] for v in cf[0]["optionValues"]])
        return v

    # Membership Level and Membership Term are dummy vals and require additional account info
    extractor = {
        "Account Current Membership Status": lambda a: a[
            "accountCurrentMembershipStatus"
        ],
        "Account ID": lambda a: a["accountId"],
        "First Name": lambda a: a["primaryContact"]["firstName"],
        "Last Name": lambda a: a["primaryContact"]["lastName"],
        "Household ID": lambda a: a.get("householdId"),
        "Company ID": lambda a: a.get("companyId"),
        "Email 1": lambda a: a["primaryContact"].get("email1"),
        "Membership Level": lambda a: None,
        "Membership Term": lambda a: None,
    }[field]
    if extractor:
        return extractor(acc)
    raise NotImplementedError(f"Extract search outputField {field} from account {acc}")


def _neon_dev_search_filter(
    field, operator, value
):  # pylint: disable=too-many-return-statements
    """Construct a filter on canned records"""
    if operator == "CONTAIN":
        if field.isdigit():  # Custom fields all indexed by number

            def custom_field_filter(rec):
                acc = first(rec, "individualAccount", "companyAccount")
                cf = [f for f in acc["accountCustomFields"] if f["id"] == field]
                if len(cf) == 0:
                    return False
                return value in [v["id"] for v in cf[0]["optionValues"]]

            return custom_field_filter

        return lambda rec: value in rec[field]

    # This could almost certainly be made less redundant
    if operator == "EQUAL":
        if field == "Email":

            def email_filter(rec):
                acc = first(rec, "individualAccount", "companyAccount")
                return True in [
                    acc["primaryContact"].get(f"email{i}") == value for i in range(1, 4)
                ]

            return email_filter
        if field == "First Name":

            def fname_filter(rec):
                acc = first(rec, "individualAccount", "companyAccount")
                return acc["primaryContact"].get("firstName") == value

            return fname_filter

        if field == "Last Name":

            def lname_filter(rec):
                acc = first(rec, "individualAccount", "companyAccount")
                return acc["primaryContact"].get("lastName") == value

            return lname_filter
        if field == "Account Current Membership Status":

            def status_filter(rec):
                acc = first(rec, "individualAccount", "companyAccount")
                return acc.get("accountCurrentMembershipStatus") == value

            return status_filter

    if operator == "NOT_EQUAL":
        if field == "Account Current Membership Status":

            def status_ne_filter(rec):
                acc = first(rec, "individualAccount", "companyAccount")
                return acc["accountCurrentMembershipStatus"] != value

            return status_ne_filter
        if field == "Email":

            def email_ne_filter(rec):
                acc = first(rec, "individualAccount", "companyAccount")
                return True not in [
                    acc["primaryContact"].get(f"email{i}") == value for i in range(1, 4)
                ]

            return email_ne_filter

    if operator == "NOT_BLANK":
        if str(field) == "150":

            def notblank_discord_filter(rec):
                acc = first(rec, "individualAccount", "companyAccount")
                for cf in acc.get("accountCustomFields", []):
                    if (
                        cf.get("id") == "150" or cf.get("name") == "Discord User"
                    ) and cf.get("value"):
                        return True
                return False

            return notblank_discord_filter

    raise NotImplementedError(
        f"dev search filter with operator {operator}, field {field}"
    )


@app.route("/v2/events/<event_id>", methods=["GET", "PATCH", "DELETE"])
def get_event(event_id):
    """Mock event endpoint for Neon"""
    if request.method == "GET":
        for row in airtable_base.get_all_records("fake_neon", "events"):
            if str(row["fields"]["eventId"]) == str(event_id):
                return row["fields"]["data"]
        return Response("Event not found", status=404)

    raise NotImplementedError(
        f"method {request.method} not implemented for /v2/events/*"
    )


@app.route("/v2/events", methods=["GET", "POST"])
def get_events():
    """Mock events endpoint for Neon"""
    # Need to implement filtering here
    if request.method == "GET":
        evts = [
            row["fields"]["data"]
            for row in airtable_base.get_all_records("fake_neon", "events")
        ]
        return {
            "events": evts,
            "pagination": {"totalPages": 1},
        }

    raise NotImplementedError(f"method {request.method} not implemented for /v2/events")


@app.route("/v2/events/<event_id>/tickets")
def get_event_tickets(event_id):
    """Mock event tickets endpoint for Neon"""
    raise NotImplementedError("TODO")


@app.route("/v2/events/<event_id>/eventRegistrations")
def get_event_registrations(event_id):
    """Mock event registrations endpoint for Neon"""
    raise NotImplementedError("TODO")


@app.route("/v2/events/<event_id>/attendees")
def get_attendees(event_id):
    """Mock event attendees endpoint for Neon"""
    result = []
    for row in airtable_base.get_all_records("fake_neon", "attendees"):
        if str(row["fields"]["eventId"]) == str(event_id):
            result.append(row["fields"]["data"])
            break
    return {
        "attendees": result,
        "pagination": {"totalResults": len(result), "totalPages": 1},
    }


@app.route("/v2/accounts/search", methods=["POST"])
def search_accounts():
    """Mock account search endpoint for Neon"""
    data = request.json
    filters = [_neon_dev_search_filter(**f) for f in data["searchFields"]]
    results = []
    for row in airtable_base.get_all_records("fake_neon", "accounts"):
        a = row["fields"]["data"]
        if False not in [f(a) for f in filters]:
            result = {}
            for k in data["outputFields"]:
                v = _neon_dev_outputify(a, k)
                if isinstance(k, int) or k.isdigit():
                    k = CustomField.from_id(k)
                result[k] = v

            results.append(result)

    return {
        "searchResults": results,
        "pagination": {
            "totalPages": 1,
            "totalResults": len(results),
        },
    }


@app.route("/v2/accounts/<account_id>", methods=["GET", "PATCH"])
def get_account(account_id):
    """Mock account lookup endpoint for Neon"""
    if request.method != "GET":
        raise NotImplementedError(
            f"Method {request.method} not implemented for /v2/accounts/*"
        )

    for row in airtable_base.get_all_records("fake_neon", "accounts"):
        if (
            str(row["fields"]["accountId"]) == str(account_id)
            and request.method == "GET"
        ):
            return row["fields"]["data"]

    return Response("Account not found", status=404)


@app.route("/v2/accounts/<account_id>/memberships")
def get_account_memberships(account_id):
    """Mock account membership endpoint for Neon"""
    for row in airtable_base.get_all_records("fake_neon", "memberships"):
        if str(row["fields"]["accountId"]) == str(account_id):
            m = row["fields"]["data"]
            return {
                "memberships": m,
                "pagination": {
                    "totalPages": 1,
                    "totalResults": len(m),
                },
            }
    return Response("Memberships not found for account", status=404)


@app.route("/v2/customFields/<field_id>", methods=["GET", "PUT"])
def get_custom_field(field_id):
    """Mock custom field endpoint for Neon"""
    raise NotImplementedError("TODO")


client = app.test_client()


def handle(method, url, data=None, headers=None):  # pylint: disable=unused-argument
    """Local execution of mock flask endpoints for Neon"""
    url = urlparse(url).path
    if method == "GET":
        return client.get(url)
    if method == "POST":
        return client.post(url, json=json.loads(data))
    if method == "DELETE":
        return client.delete(url)
    raise RuntimeError(f"method not supported: {method}")
