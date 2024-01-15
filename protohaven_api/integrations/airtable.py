"""Airtable integration (classes, tool state etc)"""
import datetime
import json
from functools import cache

import requests

from protohaven_api.config import get_config

cfg = get_config()["airtable"]
AIRTABLE_URL = "https://api.airtable.com/v0"


def get_record(base, tbl, rec):
    """Grabs a record from a named table (from config.yaml)"""
    url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}/{rec}"
    headers = {
        "Authorization": f"Bearer {cfg[base]['token']}",
        "Content-Type": "application/json",
    }
    response = requests.request("GET", url, headers=headers, timeout=5.0)
    if response.status_code != 200:
        raise RuntimeError("Airtable fetch", response.status_code, response.content)
    return json.loads(response.content)


def get_all_records(base, tbl):
    """Get all records for a given named table (ID in config.yaml)"""
    url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}"
    headers = {
        "Authorization": f"Bearer {cfg[base]['token']}",
        "Content-Type": "application/json",
    }
    records = []
    offs = ""
    while offs is not None:
        url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}?offset={offs}"
        response = requests.request("GET", url, headers=headers, timeout=5.0)
        if response.status_code != 200:
            raise RuntimeError("Airtable fetch", response.status_code, response.content)
        data = json.loads(response.content)
        records += data["records"]
        if data.get("offset") is None:
            break
        offs = data["offset"]
    return records


def insert_records(data, base, tbl):
    """Inserts one or more records into a named table"""
    url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}"
    headers = {
        "Authorization": f"Bearer {cfg[base]['token']}",
        "Content-Type": "application/json",
    }
    post_data = {"records": [{"fields": d} for d in data]}
    response = requests.request(
        "POST", url, headers=headers, data=json.dumps(post_data), timeout=5.0
    )
    return response


def update_record(data, base, tbl, rec):
    """Updates/patches a record in a named table"""
    url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}/{rec}"
    headers = {
        "Authorization": f"Bearer {cfg[base]['token']}",
        "Content-Type": "application/json",
    }
    post_data = {"fields": data}
    response = requests.request(
        "PATCH", url, headers=headers, data=json.dumps(post_data), timeout=5.0
    )
    return response


def get_class_automation_schedule():
    """Grab the current automated class schedule"""
    return get_all_records("class_automation", "schedule")


@cache
def get_instructor_log_tool_codes():
    """Fetch tool codes used in the instructor log form"""
    codes = get_all_records("class_automation", "clearance_codes")
    individual = tuple(
        c["fields"]["Form Name"] for c in codes if c["fields"].get("Individual")
    )
    return individual


def respond_class_automation_schedule(eid, pub):
    """Confirm or unconfirm a row in the Schedule table of class automation"""
    if pub:
        data = {"Confirmed": datetime.datetime.now().isoformat()}
    else:
        data = {"Confirmed": ""}
    return update_record(data, "class_automation", "schedule", eid)


def mark_schedule_supply_request(eid, missing):
    """Mark a Scheduled class as needing supplies or fully supplied"""
    return update_record(
        {"Supply State": "Supplies Requested" if missing else "Supplies Confirmed"},
        "class_automation",
        "schedule",
        eid,
    )


def mark_schedule_volunteer(eid, volunteer):
    """Mark volunteership or desire to run the Scheduled class for pay"""
    return update_record({"Volunteer": volunteer}, "class_automation", "schedule", eid)


def get_tools():
    """Get all tools in the tool DB"""
    return get_all_records("tools_and_equipment", "tools")


@cache
def get_clearance_to_tool_map():
    """Returns a mapping of clearance codes (e.g. MWB) to individual tool codes"""
    airtable_clearances = get_all_records("tools_and_equipment", "clearances")
    airtable_tools = get_all_records("tools_and_equipment", "tools")
    tool_code_by_id = {t["id"]: t["fields"]["Tool Code"] for t in airtable_tools}
    clearance_to_tool = {}
    for c in airtable_clearances:
        cc = c["fields"].get("Clearance Code")
        if cc is None:
            print(f"Skipping (missing clearance code): '{c['fields'].get('Name')}'")
            continue
        ctt = set()
        for tool_id in c["fields"].get("Tool Records", []):
            ct = tool_code_by_id.get(tool_id)
            # print(cc, tool_id, '->', ct)
            if ct is not None:
                ctt.add(ct)
        clearance_to_tool[cc] = ctt
    return clearance_to_tool
