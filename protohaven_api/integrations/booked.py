"""Functions for handling the status and reservations of tools & equipment via Booked scheduler"""
from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector

# https://github.com/protohaven/systems-integration/blob/main/airtable-automations/UpdateBookedStatus.js

STATUS_UNAVAILABLE = 2
STATUS_AVAILABLE = 1

SCHEDULE_ID = 1  # We only have one schedule

BASE_URL = "https://reserve.protohaven.org"


def resource_url(resource_id):
    """Prefill the resource URL"""
    return f"{BASE_URL}/Web/Services/Resources/{resource_id}"


def get_resource_map():
    resp = get_connector().booked_request("GET", f"{BASE_URL}/Web/Services/Resources/")
    data = resp.json()
    result = {}
    tool_code_id = get_config()["booked"]["resource_custom_attribute"]["tool_code"]
    for d in data["resources"]:
        for attr in d["customAttributes"]:
            if attr["id"] == tool_code_id and attr["value"]:
                result[attr["value"]] = d["resourceId"]
                break
    return result


def get_resource(resource_id):
    """Get the current info about a tool or equipment"""
    resp = get_connector().booked_request("GET", resource_url(resource_id))
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


def apply_resource_custom_fields(resource_id, **kwargs):
    """Applies custom fields to an existing resource.
    See https://www.bookedscheduler.com/help/api/api-resources/"""

    data = get_resource(resource_id)
    assert str(data["resourceId"]) == str(resource_id)

    # Update the customAttributes field
    field_ids = get_config()["booked"]["resource_custom_attribute"]
    # print(data['customAttributes'])
    attrs = {a["id"]: a["value"] for a in data["customAttributes"]}
    for k, v in kwargs.items():
        attrs[field_ids[k]] = v

    # Reassign to base data and push it
    data["customAttributes"] = [
        {"attributeId": k, "attributeValue": v} for k, v in attrs.items()
    ]
    print(data)
    resp = get_connector().booked_request("POST", resource_url(resource_id), json=data)
    return resp.json()


if __name__ == "__main__":
    import pytz
    from dateutil.parser import parse as parse_date

    from protohaven_api.integrations.data.connector import init as init_config

    tz = pytz.timezone("US/Eastern")

    init_config(dev=False)
    OTHERMILL_ID = 4
    name = res["name"]
    print(res["name"], "STATUSID", res["statusId"])
    input("Testing booked API - press enter to set the Othermill to unavailable")
    print(set_resource_status(OTHERMILL_ID, name, STATUS_UNAVAILABLE))
    print("STATUSID", get_resource(OTHERMILL_ID)["statusId"])
    input("enter to set available")
    print(set_resource_status(OTHERMILL_ID, name, STATUS_AVAILABLE))
    print("STATUSID", get_resource(OTHERMILL_ID)["statusId"])
    print("done")
