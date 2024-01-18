"""Functions for handling the status and reservations of tools & equipment via Booked scheduler"""
from protohaven_api.integrations.data.connector import get as get_connector

# https://github.com/protohaven/systems-integration/blob/main/airtable-automations/UpdateBookedStatus.js

STATUS_UNAVAILABLE = 2
STATUS_AVAILABLE = 1

SCHEDULE_ID = 1  # We only have one schedule

BASE_URL = "https://reserve.protohaven.org"


def resource_url(resource_id):
    """Prefill the resource URL"""
    return f"{BASE_URL}/Web/Services/Resources/{resource_id}"


def get_resource(resource_id):
    """Get the current info about a tool or equipment"""
    resp = get_connector().booked_request(resource_url(resource_id), "GET")
    return resp.json()


def set_resource_status(resource_id, resource_name, status):
    """Enable or disable a specific tool by ID"""
    resp = get_connector().booked_request(
        resource_url(resource_id),
        "POST",
        json={
            "statusId": status,
            "name": resource_name,
            "scheduleId": SCHEDULE_ID,
        },
    )
    return resp.json()


def reserve_resource(resource_id, start_time, end_time):
    """Reserve a tool or equipment for a time"""
    raise NotImplementedError("TODO")


if __name__ == "__main__":
    OTHERMILL_ID = 4
    res = get_resource(OTHERMILL_ID)
    name = res["name"]
    print(res["name"], "STATUSID", res["statusId"])
    input("Testing booked API - press enter to set the Othermill to unavailable")
    print(set_resource_status(OTHERMILL_ID, name, STATUS_UNAVAILABLE))
    print("STATUSID", get_resource(OTHERMILL_ID)["statusId"])
    input("enter to set available")
    print(set_resource_status(OTHERMILL_ID, name, STATUS_AVAILABLE))
    print("STATUSID", get_resource(OTHERMILL_ID)["statusId"])
    print("done")
