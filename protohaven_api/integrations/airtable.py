"""Airtable integration (classes, tool state etc)"""
import datetime
import json
import logging
from collections import defaultdict
from functools import cache

from dateutil import parser as dateparser

from protohaven_api.config import get_config, tz
from protohaven_api.integrations.data.connector import get as get_connector

cfg = get_config()["airtable"]
AIRTABLE_URL = "https://api.airtable.com/v0"

log = logging.getLogger("integrations.airtable")


def get_record(base, tbl, rec):
    """Grabs a record from a named table (from config.yaml)"""
    url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}/{rec}"
    response = get_connector().airtable_request(cfg[base]["token"], "GET", url)
    if response.status_code != 200:
        raise RuntimeError("Airtable fetch", response.status_code, response.content)
    return json.loads(response.content)


def get_all_records(base, tbl, suffix=None):
    """Get all records for a given named table (ID in config.yaml)"""
    records = []
    offs = ""
    while offs is not None:
        url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}?offset={offs}"
        if suffix is not None:
            url += "&" + suffix
        response = get_connector().airtable_request(cfg[base]["token"], "GET", url)
        if response.status_code != 200:
            raise RuntimeError("Airtable fetch", response.status_code, response.content)
        data = json.loads(response.content)
        records += data["records"]
        if data.get("offset") is None:
            break
        offs = data["offset"]
    return records


def get_all_records_after(base, tbl, after_date):
    """Returns a list of all records in the table with the
    Created field timestamp after a certain date"""
    return get_all_records(
        base,
        tbl,
        suffix=f"filterByFormula=IS_AFTER(%7BCreated%7D,'{after_date.isoformat()}')",
    )


def insert_records(data, base, tbl):
    """Inserts one or more records into a named table"""
    url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}"
    post_data = {"records": [{"fields": d} for d in data]}
    response = get_connector().airtable_request(
        cfg[base]["token"], "POST", url, data=json.dumps(post_data)
    )
    return response


def update_record(data, base, tbl, rec):
    """Updates/patches a record in a named table"""
    url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}/{rec}"
    post_data = {"fields": data}
    response = get_connector().airtable_request(
        cfg[base]["token"], "PATCH", url, data=json.dumps(post_data)
    )
    return response, json.loads(response.content) if response.content else None


def get_class_automation_schedule():
    """Grab the current automated class schedule"""
    return get_all_records("class_automation", "schedule")


def get_emails_notified_after(neon_id: str, after_date):
    """Gets all logged emails that were sent after a specific date,
    including their date of ontification"""
    emails = defaultdict(list)
    for row in get_all_records_after("class_automation", "email_log", after_date):
        if row["fields"].get("Neon ID", "") != str(neon_id):
            continue
        emails[row["fields"]["To"].lower()].append(
            dateparser.parse(row["fields"]["Created"])
        )
    return emails


def get_instructor_email_map():
    """Get a mapping of the instructor's full name to
    their email address, from the Capabilities automation table"""
    result = {}
    for row in get_all_records("class_automation", "capabilities"):
        if row["fields"].get("Email") is None:
            continue
        result[row["fields"]["Instructor"].strip()] = row["fields"]["Email"].strip()
    return result


def fetch_instructor_capabilities(name):
    """Fetches capabilities for a specific instructor"""
    for row in get_all_records("class_automation", "capabilities"):
        if row["fields"].get("Instructor").lower() == name.lower():
            return row
    return None


def fetch_instructor_teachable_classes():
    """Fetch teachable classes from airtable"""
    instructor_caps = defaultdict(list)
    for row in get_all_records("class_automation", "capabilities"):
        if not row["fields"].get("Instructor"):
            continue
        inst = row["fields"]["Instructor"].strip().lower()
        if "Class" in row["fields"].keys():
            instructor_caps[inst] += row["fields"]["Class"]
    return instructor_caps


DEFAULT_LOAD = 5


def fetch_instructor_max_load():
    """Fetch max teachable classes per month per instructor"""
    result = defaultdict(lambda: DEFAULT_LOAD)
    for row in get_all_records("class_automation", "capabilities"):
        if not row["fields"].get("Instructor"):
            continue
        inst = row["fields"]["Instructor"].strip()
        if "Max Class Load" in row["fields"].keys():
            result[inst] = row["fields"]["Max Class Load"]
    return result


def get_all_class_templates():
    """Get all class templates"""
    return get_all_records("class_automation", "classes")


def append_classes_to_schedule(payload):
    """Takes {Instructor, Email, Start Time, [Class]} and adds to schedule"""
    log.info(f"Append classes to schedule: {payload}")
    rep = insert_records(payload, "class_automation", "schedule")
    if rep.status_code != 200:
        raise RuntimeError(rep.content)


def log_email(neon_id, to, subject, status):
    """Logs the sending of an email in Airtable"""
    rep = insert_records(
        [{"To": to, "Subject": subject, "Status": status, "Neon ID": str(neon_id)}],
        "class_automation",
        "email_log",
    )
    if rep.status_code != 200:
        raise RuntimeError(rep.content)


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
    t = datetime.datetime.now().isoformat()
    data = {
        "Confirmed": t if pub is True else "",
        "Rejected": t if pub is False else "",
    }
    return update_record(data, "class_automation", "schedule", eid)


def apply_violation_accrual(vid, accrued):
    """Sets the Accrued value of a Violation"""
    return update_record({"Accrued": accrued}, "policy_enforcement", "violations", vid)


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


def get_areas():
    """Get all areas in the Area table"""
    return get_all_records("tools_and_equipment", "areas")


def get_all_maintenance_tasks():
    """Get all recurring maintenance tasks in the tool DB"""
    return get_all_records("tools_and_equipment", "recurring_tasks")


def update_recurring_task_date(task_id, date):
    """Updates the last-scheduled date on a specific recurring task"""
    return update_record(
        {"Last Scheduled": date.strftime("%Y-%m-%d")},
        "tools_and_equipment",
        "recurring_tasks",
        task_id,
    )


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


def get_shop_tech_time_off():
    """Gets reported time off by techs"""
    return get_all_records("neon_data", "shop_tech_time_off")


def get_announcements_after(d, roles):
    """Gets all announcements, excluding those before `d`"""
    result = []
    for row in get_all_records("neon_data", "sign_in_announcements"):
        adate = dateparser.parse(
            row["fields"].get("Published", "2024-01-01")
        ).astimezone(tz)
        print(row["fields"])
        if adate <= d:
            continue
        for r in row["fields"]["Roles"]:
            print(r, "in", roles, "?")
            if r in roles:
                result.append(row["fields"])
                break
    return result


def get_policy_sections():
    """Gets all sections of policy that require enforcement"""
    return get_all_records("policy_enforcement", "sections")


def get_policy_violations():
    """Returns all policy violations"""
    rows = get_all_records("policy_enforcement", "violations")
    return [v for v in rows if v["fields"].get("Onset")]


def open_violation(
    reporter, suspect, sections, evidence, onset, fee, notes
):  # pylint: disable=too-many-arguments
    """Opens a new violation with a fee schedule and/or suspension"""
    section_map = {s["fields"]["id"]: s["id"] for s in get_policy_sections()}
    return insert_records(
        [
            {
                "Reporter": reporter,
                "Suspect": suspect,
                "Relevant Sections": [section_map[int(s)] for s in sections],
                "Evidence": evidence,
                "Onset": onset.isoformat(),
                "Daily Fee": fee,
                "Notes": notes,
            }
        ],
        "policy_enforcement",
        "violations",
    )


def close_violation(instance, closer, resolution, suspect, notes):
    """Close out a violation, with potentially some notes"""
    match = [
        p for p in get_policy_violations() if p["fields"]["Instance #"] == instance
    ]
    if len(match) != 1:
        raise RuntimeError(
            "No matching violation with instance number " + str(instance)
        )
    data = {
        "Closer": closer,
        "Closing Notes": notes,
        "Resolution": resolution.isoformat(),
    }
    if suspect is not None:
        data["Suspect"] = suspect
    return update_record(data, "policy_enforcement", "violations", match[0]["id"])


def get_policy_suspensions():
    """Gets all suspensions due to policy violation"""
    rows = get_all_records("policy_enforcement", "suspensions")
    return [s for s in rows if s["fields"].get("Start Date")]


def create_suspension(neon_id, violations, start_date, end_date):
    """Create a new suspension spanning `start_date` to `end_date`"""
    data = [
        {
            "Neon ID": neon_id,
            "Relevant Violations": violations,
            "Start Date": start_date.isoformat(),
            "End Date": end_date.isoformat(),
        }
    ]
    return insert_records(data, "policy_enforcement", "suspensions")


def get_lapsed_suspensions():
    """Return all suspensions that have ended, but haven't yet been reinstated."""
    raise NotImplementedError()


def get_policy_fees():
    """Returns all fees in the table"""
    rows = get_all_records("policy_enforcement", "fees")
    return [f for f in rows if f["fields"].get("Created")]


def create_fees(fees):
    """Create fees for each violation and fee amount in the map"""
    data = [{"Created": t, "Violation": [vid], "Amount": amt} for vid, amt, t in fees]
    return insert_records(data, "policy_enforcement", "fees")


def pay_fee(fee_id):
    """Mark fee as paid"""
    raise NotImplementedError()
