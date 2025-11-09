"""A mock version of Neon CRM serving results pulled from Nocodb"""

import json
import logging
from dataclasses import dataclass
from random import random
from urllib.parse import urlparse

from flask import Flask, Response, request

from protohaven_api.config import safe_parse_datetime
from protohaven_api.integrations import airtable_base
from protohaven_api.integrations.data.neon import CustomField

app = Flask(__file__)

log = logging.getLogger("integrations.data.dev_neon")


def get_all_rows(table: str):
    """Fetches all rows in a table, throwing hint error if table missing"""
    try:
        return airtable_base.get_all_records("fake_neon", table)
    except airtable_base.TableNotFoundError as e:
        raise RuntimeError(
            "Table not found; Hint: have you ran "
            + "./nocodb/init_or_update_nocodb.sh?"
        ) from e
    except Exception as e:
        raise e


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
        "Preferred Name": lambda a: a["primaryContact"].get("preferredName"),
        "Household ID": lambda a: a.get("householdId"),
        "Company ID": lambda a: a.get("companyId"),
        "Email 1": lambda a: a["primaryContact"].get("email1"),
        "Membership Level": lambda a: None,
        "Membership Term": lambda a: None,
    }[field]
    if extractor:
        return extractor(acc)
    raise NotImplementedError(f"Extract search outputField {field} from account {acc}")


def _neon_dev_search_filter(  # pylint: disable=too-many-return-statements, too-many-branches
    field, operator, value
):
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
                    (acc["primaryContact"].get(f"email{i}") or "").strip().lower()
                    == value.strip().lower()
                    for i in range(1, 4)
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
        if field == "Account ID":

            def aid_ne_filter(rec):
                acc = first(rec, "individualAccount", "companyAccount")
                return str(acc.get("accountId")) != str(value)

            return aid_ne_filter

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


@app.route("/v2/events/search", methods=["POST"])
def search_event():
    """Crude search mocker for events - does not respect output fields"""
    data = request.json
    from_date = None
    until_date = None
    for f in data["searchFields"]:
        if f["field"] == "Event Start Date":
            if f["operator"] == "GREATER_AND_EQUAL":
                from_date = safe_parse_datetime(f["value"])
            elif f["operator"] == "LESS_AND_EQUAL":
                until_date = safe_parse_datetime(f["value"])
            else:
                raise RuntimeError(
                    f"Unhandled operator {f['operator']} for field {f['field']}"
                )

    assert from_date and until_date
    output_map = {
        "Event ID": "id",
        "Event Name": "name",
        "Event Capacity": "capacity",
        "Event Start Date": "startDate",
        "Event Start Time": "startTime",
    }
    result = []
    for row in get_all_rows("events"):
        row = row["fields"]["data"]
        if not row:
            continue
        assert isinstance(row, dict)
        d = safe_parse_datetime(f"{row['startDate']} {row['startTime']}")
        if from_date <= d <= until_date:
            result.append({name: row[field] for name, field in output_map.items()})
            result[-1][
                "Event Registration Attendee Count"
            ] = 1  # Need to actually handle this eventually
            result[-1]["Event Web Publish"] = "Yes" if row["publishEvent"] else "No"
            result[-1]["Event Web Register"] = (
                "Yes" if row["enableEventRegistrationForm"] else "No"
            )
    return {
        "searchResults": result,
        "pagination": {"totalResults": len(result), "totalPages": 1},
    }


@app.route("/v2/events/<event_id>", methods=["GET", "PATCH", "DELETE"])
def get_event(event_id):
    """Mock event endpoint for Neon"""
    # Note that fetching an event directly returns structured data,
    # while searching for events returns a flattened and reduced set of data
    for row in get_all_rows("events"):
        if str(row["fields"]["eventId"]) == str(event_id):
            if request.method == "GET":
                return row["fields"]["fetch_data"]
            if request.method == "DELETE":
                _, content = airtable_base.delete_record(
                    "fake_neon", "events", row["id"]
                )
                return content
            raise NotImplementedError(
                f"method {request.method} not implemented for /v2/events/*"
            )
    return Response("Event not found", status=404)


@app.route("/v2/events", methods=["GET", "POST"])
def get_events():
    """Mock events endpoint for Neon"""
    # Need to implement filtering here
    if request.method == "GET":
        evts = [
            row["fields"]["data"]
            for row in get_all_rows("events")
            if row["fields"]["data"]
        ]
        return {
            "events": evts,
            "pagination": {"totalPages": 1},
        }

    # POST
    new_id = int(random() * 100000)
    airtable_base.insert_records(
        [
            {
                "eventId": new_id,
                "data": json.dumps(request.json),
            }
        ],
        "fake_neon",
        "events",
    )
    return {"id": new_id}


@app.route("/v2/events/<event_id>/tickets")
def get_event_tickets(event_id):
    """Mock event tickets endpoint for Neon"""
    for row in get_all_rows("fake_neon"):
        if not row["fields"]["data"]:
            continue
        if str(row["fields"]["eventId"]) == str(event_id):
            # Weird that Neon doesn't paginate these results, but a lot of their
            # API is inconsistent with itself, so ¯\_(ツ)_/¯
            return row["fields"]["data"]
    return []


@app.route("/v2/events/<event_id>/eventRegistrations")
def get_event_registrations(event_id):
    """Mock event registrations endpoint for Neon"""
    raise NotImplementedError("TODO")


@app.route("/v2/events/<event_id>/attendees")
def get_attendees(event_id):
    """Mock event attendees endpoint for Neon"""
    result = []
    for row in get_all_rows("attendees"):
        if not row["fields"]["data"]:
            continue
        if str(row["fields"]["eventId"]) == str(event_id):
            result += row["fields"]["data"]
            break
    return {
        "attendees": result,
        "pagination": {"totalResults": len(result), "totalPages": 1},
    }


@app.route("/v2/accounts/search", methods=["POST"])
def search_accounts():
    """Mock account search endpoint for Neon"""
    data = request.json
    log.info(data)
    filters = [_neon_dev_search_filter(**f) for f in data["searchFields"]]
    results = []
    for row in get_all_rows("accounts"):
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


def _merge_account_data(dest, src):
    assert "individualAccount" in dest
    for k in src["individualAccount"].keys():
        if k == "accountCustomFields":
            continue
        dest[k] = src[k]  # Probably not entirely correct; needs refinement

    scf = src["individualAccount"].get("accountCustomFields") or []
    scf_ids = {cf["id"] for cf in scf}
    dest["individualAccount"]["accountCustomFields"] = [
        cf
        for cf in (dest["individualAccount"].get("accountCustomFields") or [])
        if cf["id"] not in scf_ids
    ] + scf
    return dest


@app.route("/v2/accounts/<account_id>", methods=["GET", "PATCH"])
def get_account(account_id):
    """Mock account lookup endpoint for Neon"""
    for row in get_all_rows("accounts"):
        if str(row["fields"]["accountId"]) != str(account_id):
            continue
        if request.method == "GET":
            return row["fields"]["data"]
        if request.method == "PATCH":
            # Note: this isn't a deep merge
            merged_data = _merge_account_data(row["fields"]["data"], request.json)
            return str(
                airtable_base.update_record(
                    {"data": merged_data}, "fake_neon", "accounts", row["id"]
                )
            )

    return Response("Account not found", status=404)


@app.route("/v2/accounts/<account_id>/memberships")
def get_account_memberships(account_id):
    """Mock account membership endpoint for Neon"""
    m = []
    for row in get_all_rows("memberships"):
        if str(row["fields"]["accountId"]) == str(account_id):
            m = row["fields"]["data"]
            break
    return {
        "memberships": m,
        "pagination": {
            "totalPages": 1,
            "totalResults": len(m),
        },
    }


@app.route("/login", methods=["GET", "POST"])
def login_handler():
    """Dummy login page handler for user impersonation"""
    if request.method == "GET":
        return '<head><meta name="csrf-token" content="test_csrf_token"/></head>'
    return "OK - Log Out"


@app.route("/np/ssoAuth")
def sso_auth_handler():
    """Dummy SSO authentication handler for user impersonation"""
    return "Mission Control Dashboard"


@app.route("/event/newPackage.do")
def new_ticket_package():
    """Dummy handler for ticket group editing"""
    return "Event Price"


@app.route("/event/savePackage.do")
def save_ticket_package():
    """Dummy handler for ticket group editing"""
    return Response("Creatin'", status=302)


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
    if method == "PATCH":
        return client.patch(url, json=json.loads(data))
    raise RuntimeError(f"method not supported: {method}")


@dataclass
class DevSeshResp:
    """Requests-style response"""

    status_code: int
    content: bytes


class Session:
    """A requests-style session for dev environment"""

    def get(self, *args, **kwargs):
        """Return a requests-style response"""
        r = client.get(*args, **kwargs)
        return DevSeshResp(status_code=r.status_code, content=r.data)

    def post(self, *args, **kwargs):
        """Return a requests-style response"""
        r = client.post(*args, **kwargs)
        return DevSeshResp(status_code=r.status_code, content=r.data)
