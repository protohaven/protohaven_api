"""Functions for handling the status and reservations of tools & equipment via Booked scheduler"""
from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector

# https://github.com/protohaven/systems-integration/blob/main/airtable-automations/UpdateBookedStatus.js

STATUS_UNAVAILABLE = 2
STATUS_AVAILABLE = 1

TYPE_TOOL = 8
# TYPE_AREA =

SCHEDULE_ID = 1  # We only have one schedule

BASE_URL = "https://reserve.protohaven.org"


def resource_url(resource_id):
    """Prefill the resource URL"""
    return f"{BASE_URL}/Web/Services/Resources/{resource_id}"


def _config_attribs():
    return get_config()["booked"]["resource_custom_attribute"]


def get_resource_map():
    """Fetches a map from a resource tool code to its ID"""
    resp = get_connector().booked_request("GET", f"{BASE_URL}/Web/Services/Resources/")
    data = resp.json()
    result = {}
    tool_code_id = _config_attribs()["tool_code"]
    for d in data["resources"]:
        for attr in d["customAttributes"]:
            if attr["id"] == tool_code_id and attr["value"]:
                result[attr["value"]] = d["resourceId"]
                break
    return result


def get_resource_group_map():
    """Gets the map of resource name to its Booked `resourceId`"""
    resp = get_connector().booked_request(
        "GET", f"{BASE_URL}/Web/Services/Resources/Groups"
    )
    data = resp.json()
    result = {}
    for d in data["groups"]:
        result[d["name"]] = d["id"]
    return result


def get_resource(resource_id):
    """Get the current info about a tool or equipment"""
    c = get_connector()
    print(c)
    resp = get_connector().booked_request("GET", resource_url(resource_id))
    print("RESP", resp)
    return resp.json()


def set_resource_status(resource_id, resource_name, status):
    """Enable or disable a specific tool by ID"""
    resp = get_connector().booked_request(
        "POST",
        resource_url(resource_id),
        json={
            "statusId": status,
            "name": resource_name,
            "scheduleId": SCHEDULE_ID,
        },
    )
    return resp.json()


def get_reservations(start, end):
    """Get all reservations within the start and end times"""
    url = f"{BASE_URL}/Web/Services/Reservations/?startDateTime={start.isoformat()}&endDateTime={end.isoformat()}"  # pylint: disable=line-too-long
    resp = get_connector().booked_request("GET", url)
    return resp.json()


def reserve_resource(
    resource_id,
    start_time,
    end_time,
    title="System Reserved",
    desc="api.protohaven.org reservation",
):
    """Reserve a tool or equipment for a time"""
    url = f"{BASE_URL}/Web/Services/Reservations/"
    resp = get_connector().booked_request(
        "POST",
        url,
        json={
            "description": desc,
            "endDateTime": end_time.isoformat(),
            "resourceId": resource_id,
            "startDateTime": start_time.isoformat(),
            "title": title,
            "userId": 103,  # system@protohaven.org
        },
    )
    return resp.json()


def apply_resource_custom_fields(resource, **kwargs):
    """Applies custom fields to an existing resource. Pass
    either the resource ID or a dict of the object data
    See https://www.bookedscheduler.com/help/api/api-resources/"""

    if isinstance(resource, dict):
        data = resource
    else:
        data = get_resource(resource)
        assert str(data["resourceId"]) == str(resource)

    # Update the customAttributes field
    field_ids = _config_attribs()
    attrs = {a["id"]: a["value"] for a in data["customAttributes"]}
    for k, v in kwargs.items():
        attrs[field_ids[k]] = v

    # Reassign to base data and push it
    data["customAttributes"] = [
        {"attributeId": k, "attributeValue": v} for k, v in attrs.items()
    ]
    resp = get_connector().booked_request(
        "POST", resource_url(data["resourceId"]), json=data
    )
    return resp.json()


def create_resource(name):
    """Creates a named resource and returns the creation result"""
    # Not sure how many of these fields are needed - there are more as well.
    resp = get_connector().booked_request(
        "POST",
        f"{BASE_URL}/Web/Services/Resources/",
        json={
            "name": name,
            "requiresApproval": False,
            "allowMultiday": False,
            "scheduleId": 1,
            "statusId": "1",
            "typeId": "8",
            "autoReleaseMinutes": None,
            "requiresCheckIn": False,
            "maxConcurrentReservations": 1,
            "extendIfMissedCheckout": False,
        },
    )
    return resp.json()
