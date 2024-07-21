"""A mock version of Neon CRM serving results pulled from mock_data"""

from protohaven_api.integrations.data.loader import mock_data
from protohaven_api.integrations.data.neon import CustomField, URL_BASE
from flask import Flask, request, Response

app = Flask(__file__)


def first(*args):
    d = args[0]
    for k in args[1:]:
        v = d.get(k)
        if v is not None:
            return v
    return None

def _neon_dev_outputify(rec, field):
    acc = first(rec, 'individualAccount', 'companyAccount')
    if isinstance(field, int) or field.isdigit(): # Custom fields have integer ids
        cf = [f for f in acc['accountCustomFields'] if str(f['id']) == str(field)]
        if len(cf) == 0:
            return None
        if cf[0].get('value') is not None:
            return cf[0]['value']
        else:
            v = "|".join([v['name'] for v in cf[0]['optionValues']])
            return v

    extractor = {
            "Account Current Membership Status": lambda a: a['accountCurrentMembershipStatus'],
            "Account ID": lambda a: a['accountId'],
            "First Name": lambda a: a['primaryContact']['firstName'],
            "Last Name": lambda a: a['primaryContact']['lastName'],
            "Household ID": lambda a: a.get('householdId'),
            "Company ID": lambda a: a.get('companyId'),
            "Email 1": lambda a: a['primaryContact'].get('email1'),
            "Membership Level": lambda a: None, # TODO requires additional account info
            "Membership Term": lambda a: None, # TODO also
        }[field]
    if extractor: 
        return extractor(acc)
    raise NotImplementedError(f"Extract search outputField {field} from account {acc}")

def _neon_dev_search_filter(field, operator, value):
    if operator == "CONTAIN":
        if field.isdigit(): # Custom fields all indexed by number
            def custom_field_filter(rec):
                acc = first(rec, 'individualAccount', 'companyAccount')
                cf = [f for f in acc['accountCustomFields'] if f['id'] == field]
                if len(cf) == 0:
                    return False
                return value in [v['id'] for v in cf[0]['optionValues']]
            return custom_field_filter

        return lambda rec: value in rec[field]
    elif operator == "EQUAL":
        if field == "Email":
            def email_filter(rec):
                acc = first(rec, 'individualAccount', 'companyAccount')
                return True in [acc['primaryContact'][f'email{i}'] == value for i in range(1, 4)]
            return email_filter
        elif field == "First Name":
            def fname_filter(rec):
                acc = first(rec, 'individualAccount', 'companyAccount')
                return acc['primaryContact']['firstName'] == value
            return fname_filter
    else:
        raise NotImplementedError(f"dev search filter with operator {operator}")

@app.route("/events/<event_id>", methods=["GET", "PATCH"])
def get_event(event_id):
    if request.method == "GET":
        for e in mock_data["neon"]["events"]:
            if str(e['id']) == str(event_id):
                return e
        return Response("Event not found", status=404)
    raise NotImplementedError("PATCH")


@app.route("/events")
def get_events():
    return {
        "events": mock_data["neon"]["events"],
        "pagination": {"totalPages": 1},
    }


@app.route("/events/<event_id>/tickets")
def get_event_tickets(event_id):
    raise NotImplementedError("TODO")


@app.route("/events/<event_id>/eventRegistrations")
def get_event_registrations(event_id):
    raise NotImplementedError("TODO")


@app.route("/events/<event_id>/attendees")
def get_attendees():
    raise NotImplementedError("TODO")

@app.route("/accounts/search", methods=["POST"])
def search_accounts():
    data = request.json
    filters = [_neon_dev_search_filter(**f) for f in data["searchFields"]]
    results = []
    for a in mock_data['neon']['accounts']:
        if False not in [f(a) for f in filters]:
            result = {}
            for k in data['outputFields']:
                v = _neon_dev_outputify(a, k)
                if isinstance(k, int) or k.isdigit():
                    k = CustomField.fromId(k)
                result[k] = v

            results.append(result) 

    return {
             
            "searchResults": results,
            "pagination": {
                "totalPages": 1,
                "totalResults": len(results),
            },
    }


@app.route("/accounts/<account_id>", methods=["GET, PATCH"])
def get_account(account_id):
    raise NotImplementedError("TODO")


@app.route("/accounts/<account_id>/memberships")
def get_account_memberships(account_id):
    raise NotImplementedError("TODO")


@app.route("/customFields/<field_id>", methods=["GET", "PUT"])
def get_custom_field(field_id):
    raise NotImplementedError("TODO")

client = app.test_client()

def handle(*args, **kwargs):
    args = list(args)
    args[0] = args[0].replace(URL_BASE, "") # TODO: use pathlib instead for more futureproofedness
    if args[1] == "GET":
        return client.get(*args, **kwargs)
    elif args[1] == "POST":
        return client.post(*args, **kwargs)

