"""Functions for handling the status and reservations of tools & equipment via Booked scheduler"""

import datetime
import logging
import secrets
from collections import defaultdict

from protohaven_api.config import get_config, tznow
from protohaven_api.integrations.data.connector import get as get_connector
from protohaven_api.integrations.data.warm_cache import WarmDict

log = logging.getLogger("booked")

# https://github.com/protohaven/systems-integration/blob/main/airtable-automations/UpdateBookedStatus.js
STATUS_UNAVAILABLE = 2
STATUS_AVAILABLE = 1


def get_resources():
    """Fetches all resources"""
    return get_connector().booked_request("GET", "/Resources/")["resources"]


def get_resource_id_to_name_map():
    """Gets the mapping of resource IDs to the tool name"""
    return {d["resourceId"]: d["name"] for d in get_resources()}


def get_resource_map():
    """Fetches a map from a resource tool code to its ID"""
    result = {}
    tool_code_id = get_config("booked/resource_custom_attribute/tool_code")
    for d in get_resources():
        for attr in d["customAttributes"]:
            if attr["id"] == tool_code_id and attr["value"]:
                result[attr["value"]] = d["resourceId"]
                break
    return result


def get_resource_group_map():
    """Gets the map of resource name to its Booked `resourceId`"""
    data = get_connector().booked_request("GET", "/Resources/Groups")
    result = {}
    for d in data["groups"]:
        result[d["name"]] = d["id"]
    return result


def get_resource(resource_id):
    """Get the current info about a tool or equipment"""
    return get_connector().booked_request("GET", f"/Resources/{resource_id}")


def set_resource_status(resource_id, status):
    """Enable or disable a specific tool by ID"""
    # We must get the name of the resource in order to set its status, unfortunately.
    data = get_resource(resource_id)
    assert data.get("name", None) is not None

    return get_connector().booked_request(
        "POST",
        f"/Resources/{resource_id}",
        json={
            "statusId": status,
            "name": data["name"],
            "scheduleId": get_config("booked/schedule_id"),
        },
    )


def get_members_group():
    """Fetches group info by ID"""
    group_id = get_config("booked/members_group_id")
    g = get_connector().booked_request("GET", f"/Groups/{group_id}")
    if not g:
        raise RuntimeError(f"Members group not found - ID {group_id}")
    return g


def get_members_group_tool_permissions():
    """Fetches the IDs of all tools that users in the Members group are permitted to use"""
    for p in get_members_group()["permissions"]:
        yield int(p.split("/")[-1])  # Form of '/Web/Services/Resources/1'


def set_members_group_tool_permissions(tool_ids):
    """Sets the list of permitted tools for the Members group"""
    gid = get_config("booked/members_group_id")
    return get_connector().booked_request(
        "POST",
        f"/Groups/{gid}/Permissions",
        json={
            "permissions": [int(t) for t in tool_ids],
        },
    )


def get_reservations(start, end):
    """Get all reservations within the start and end times"""
    url = f"/Reservations/?startDateTime={start.isoformat()}&endDateTime={end.isoformat()}"
    return get_connector().booked_request("GET", url)


def delete_reservation(refnum):
    """Deletes a reservation by its reference number - be very careful with
    this one!"""
    url = f"/Reservations/{refnum}"
    return get_connector().booked_request("DELETE", url)


def reserve_resource(
    resource_id,
    start_time,
    end_time,
    title="System Reserved",
    desc="api.protohaven.org reservation",
):
    """Reserve a tool or equipment for a time"""
    return get_connector().booked_request(
        "POST",
        "/Reservations/",
        json={
            "description": desc,
            "endDateTime": end_time.isoformat(),
            "resourceId": resource_id,
            "startDateTime": start_time.isoformat(),
            "title": title,
            "userId": 103,  # system@protohaven.org
        },
    )


def update_resource(data):
    """Updates a resource given a dict of data"""
    return get_connector().booked_request(
        "POST", f"/Resources/{data['resourceId']}", json=data
    )


def stage_custom_attributes(resource, **kwargs):
    """Makes modifications to the customAttributes field of a resource dict.
    returns `True` for `changed` if any fields were actually modified"""
    field_ids = get_config("booked/resource_custom_attribute")
    changed = {}
    attrs = {a["id"]: a["value"] for a in resource["customAttributes"]}
    for k, v in kwargs.items():
        changed[k] = attrs.get(field_ids[k]) != v
        attrs[field_ids[k]] = v
    resource["customAttributes"] = [
        {"attributeId": k, "attributeValue": v} for k, v in attrs.items()
    ]
    return resource, changed


def _fmt_update(k, v):
    if k != "statusId":
        return v
    return "AVAILABLE" if v == STATUS_AVAILABLE else "NOT_AVAILABLE"


def stage_tool_update(r, custom_attributes, reservable=True, **kwargs):
    """Computes changes and an updated record object based on the custom
    attrs and kwargs applied"""
    kwargs["statusId"] = STATUS_AVAILABLE if reservable else STATUS_UNAVAILABLE
    kwargs["typeId"] = str(get_config("booked/tool_type_id"))

    changes = []
    r, changed_attrs = stage_custom_attributes(r, **custom_attributes)
    if True in changed_attrs.values():
        changes.append(f"custom attributes ({changed_attrs} -> {custom_attributes})")
        log.warning(
            f"Changed custom attributes: {changed_attrs} -> {custom_attributes}"
        )
    for k, v in kwargs.items():
        if str(r.get(k)) != str(v):
            changes.append(f"{k} ({_fmt_update(k,r.get(k))}->{_fmt_update(k,v)})")
            log.warning(changes[-1])
            r[k] = v
    return r, changes


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
    field_ids = get_config("booked/resource_custom_attribute")
    attrs = {a["id"]: a["value"] for a in data["customAttributes"]}
    for k, v in kwargs.items():
        attrs[field_ids[k]] = v

    # Reassign to base data and push it
    data["customAttributes"] = [
        {"attributeId": k, "attributeValue": v} for k, v in attrs.items()
    ]
    return get_connector().booked_request(
        "POST", f"/Resources/{data['resourceId']}", json=data
    )


def create_resource(name):
    """Creates a named resource and returns the creation result"""
    # Not sure how many of these fields are needed - there are more as well.
    return get_connector().booked_request(
        "POST",
        "/Resources/",
        json={
            "name": name,
            "requiresApproval": False,
            "allowMultiday": False,
            "scheduleId": get_config("booked/schedule_id"),
            "statusId": str(STATUS_AVAILABLE),
            "typeId": str(get_config("booked/tool_type_id")),
            "autoReleaseMinutes": None,
            "requiresCheckIn": False,
            "maxConcurrentReservations": 1,
            "extendIfMissedCheckout": False,
            "autoAssignPermissions": True,
        },
    )


def create_user_as_member(fname, lname, email):
    """Creates a new user in Booked, with the Members group added"""
    return get_connector().booked_request(
        "POST",
        "/Users/",
        json={
            "firstName": fname,
            "lastName": lname,
            "emailAddress": email,
            "userName": email,
            "timezone": "America/New_York",
            "password": secrets.token_urlsafe(32),  # required, but not used (OAuth)
            "language": "en_us",
            "groups": [int(get_config("booked/members_group_id"))],
        },
    )


def get_all_users():
    """Gets all users in Booked"""
    return get_connector().booked_request("GET", "/Users/")["users"]


def get_user(user_id):
    """Fetches an individual user from Booked"""
    return get_connector().booked_request("GET", f"/Users/{user_id}")


def update_user(user_id, data):
    """Updates a user in Booked (see `get_user` for data)"""
    return get_connector().booked_request("POST", f"/Users/{user_id}", json=data)


def assign_members_group_users(user_ids: list):
    """Given a list of Booked User IDs, set them as belonging to
    the Members group so they can access Member tools."""
    gid = get_config("booked/members_group_id")
    return get_connector().booked_request(
        "POST",
        f"/Groups/{gid}/Users",
        json={
            "userIds": [int(uid) for uid in user_ids],
        },
    )


class ReservationCache(WarmDict):
    """Fetches tool reservation info"""

    NAME = "reservations"
    REFRESH_PD_SEC = datetime.timedelta(minutes=5).total_seconds()
    RETRY_PD_SEC = datetime.timedelta(minutes=5).total_seconds()

    def __init__(self, update_cb):
        self.cb = update_cb
        super().__init__()

    def refresh(self):
        start = tznow()
        end = start.replace(hour=23, minute=59, second=59)
        self["reservations"] = get_reservations(start, end)["reservations"]
        self.log.debug("Reservation cache updated")
        self.cb(self)
        # We can be less aggressive outside of normal business hours
        self.REFRESH_PD_SEC = datetime.timedelta(  # pylint: disable=invalid-name
            minutes=15 if 10 <= start.hour <= 22 else 60
        ).total_seconds()

    def get_today_reservations_by_tool(self):
        """Fetches today's reservations, keyed by tool code"""
        tool_code_attr = get_config("booked/resource_custom_attribute/tool_code")
        result = defaultdict(list)
        for r in self["reservations"]:
            tool_code = [
                a["value"] for a in r["customAttributes"] if a["id"] == tool_code_attr
            ]
            if len(tool_code) == 1:
                result[tool_code[0]].append(
                    {
                        "ref": r["referenceNumber"],
                        "user": r["userId"],
                        "start": r["startDate"],
                        "end": r["endDate"],
                    }
                )
        return result
