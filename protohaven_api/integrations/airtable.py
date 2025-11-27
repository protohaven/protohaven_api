"""Airtable integration (classes, tool state etc)"""

import datetime
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

from dateutil import parser as dateparser
from dateutil.rrule import rrulestr

from protohaven_api.config import get_config, safe_parse_datetime, tz, tznow
from protohaven_api.integrations.airtable_base import (
    _idref,
    delete_record,
    get_all_records,
    get_all_records_after,
    get_all_records_between,
    get_record,
    insert_records,
    update_record,
)
from protohaven_api.integrations.data.warm_cache import WarmDict
from protohaven_api.integrations.models import SignInEvent

log = logging.getLogger("integrations.airtable")

type NeonID = int
type ToolCode = str
type RecordID = str
type ForecastOverride = tuple[str, list[str], str]


def get_class_automation_schedule():
    """Grab the current automated class schedule"""
    return get_all_records("class_automation", "schedule")


def get_scheduled_class(rec):
    """Get the specific scheduled class row by reference"""
    return get_record("class_automation", "schedule", rec)


def get_notifications_after(tag, after_date):
    """Gets all logged targets that were sent after a specific date,
    including their date of ontification"""
    targets = defaultdict(list)
    for row in get_all_records_after("class_automation", "email_log", after_date):
        row_tag = row["fields"].get("Neon ID", "").strip()
        if isinstance(tag, re.Pattern):
            if tag.match(row_tag) is None:
                continue
        elif row_tag != str(tag):
            continue
        targets[row["fields"]["To"].lower()].append(
            safe_parse_datetime(row["fields"]["Created"])
        )
    return targets


def get_instructor_email_map(require_teachable_classes=False, require_active=False):
    """Get a mapping of the instructor's full name to
    their email address, from the Capabilities automation table"""
    result = {}
    for row in get_all_records("class_automation", "capabilities"):
        if row["fields"].get("Email") is None:
            continue
        if require_teachable_classes:
            classes = row["fields"].get("Class") or []
            if (isinstance(classes, int) and classes > 0) or len(classes) == 0:
                continue
        if require_active and not row["fields"].get("Active"):
            continue
        result[row["fields"]["Instructor"].strip()] = row["fields"]["Email"].strip()
    return result


def fetch_instructor_capabilities(name):
    """Fetches capabilities for a specific instructor"""
    for row in get_all_records("class_automation", "capabilities"):
        if row["fields"].get("Instructor").lower() == name.lower():
            return row
    return None


NOCODB_CLASS_REF_FIELD = (
    "_nc_m2m_Class_Templates_Instructor_Capas",
    "Class_Templates_id",
)


def fetch_instructor_teachable_classes():
    """Fetch teachable classes from airtable"""
    instructor_caps = defaultdict(list)
    for row in get_all_records("class_automation", "capabilities"):
        if not row["fields"].get("Instructor"):
            continue
        inst = row["fields"]["Instructor"].strip().lower()
        if "Class" in row["fields"].keys():
            if NOCODB_CLASS_REF_FIELD[0] in row["fields"]:
                instructor_caps[inst] += [
                    str(lnk[NOCODB_CLASS_REF_FIELD[1]])
                    for lnk in row["fields"][NOCODB_CLASS_REF_FIELD[0]]
                ]
            else:
                instructor_caps[inst] += _idref(row, "Class")
    return instructor_caps


def get_all_class_templates():
    """Get all class templates"""
    return get_all_records("class_automation", "classes")


def append_classes_to_schedule(payload):
    """Takes {Instructor, Email, Start Time, [Class]} and adds to schedule"""
    assert isinstance(payload, list)
    return insert_records(
        payload, "class_automation", "schedule", link_fields=["Class"]
    )


def get_role_intents():
    """Get all pending Discord role changes"""
    return get_all_records("people", "automation_intents")


def log_intents_notified(intents):
    """Update intent log record with the current timestamp"""
    for intent in intents:
        update_record(
            {"Last Notified": tznow().isoformat()},
            "people",
            "automation_intents",
            intent,
        )


def log_comms(tag, to, subject, status):
    """Logs the sending of comms in Airtable"""
    status, content = insert_records(
        [{"To": to, "Subject": subject, "Status": status, "Neon ID": str(tag)}],
        "class_automation",
        "email_log",
    )
    if status != 200:
        raise RuntimeError(content)


@lru_cache(maxsize=1)
def get_instructor_log_tool_codes():
    """Fetch tool codes used in the instructor log form"""
    codes = get_all_records("class_automation", "clearance_codes")
    individual = tuple(
        c["fields"]["Form Name"] for c in codes if c["fields"].get("Individual")
    )
    return individual


def respond_class_automation_schedule(eid, pub):
    """Confirm or unconfirm a row in the Schedule table of class automation"""
    t = tznow().isoformat()
    data = {
        "Confirmed": t if pub is True else "",
        "Rejected": t if pub is False else "",
    }
    return update_record(data, "class_automation", "schedule", eid)


def apply_violation_accrual(vid, accrued):
    """Sets the Accrued value of a Violation"""
    return update_record({"Accrued": accrued}, "policy_enforcement", "violations", vid)


def set_booked_resource_id(airtable_id, resource_id):
    """Set the Booked resource ID for a given tool"""
    return update_record(
        {"BookedResourceId": resource_id},
        "tools_and_equipment",
        "tools",
        airtable_id,
    )


def mark_schedule_supply_request(eid, state):
    """Mark a Scheduled class as needing supplies or fully supplied"""
    return update_record(
        {"Supply State": state},
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


@dataclass
class RecertConfig:  # pylint: disable=too-few-public-methods
    """All metadata used to inform whether or not a member's clearance should undergo
    recertification, and how the recert happens (e.g. quiz vs instruction)"""

    tool: ToolCode
    quiz_url: str
    expiration: datetime.timedelta
    bypass_hours: int
    bypass_tools: set[ToolCode]
    bypass_cutoff: datetime.timedelta


def get_tool_recert_configs_by_code():
    """Returns formatted recertification configs, keyed by tool code"""
    tool_configs = {}
    cutoff = datetime.timedelta(
        days=int(get_config("general/recertification/bypass_hours_window_days"))
    )
    for t in get_tools():
        cfg = RecertConfig(
            tool=t["fields"]["Tool Code"],
            quiz_url=t["fields"]["Recert Quiz"],
            expiration=datetime.timedelta(
                days=t["fields"]["Days until Recert Needed"] or 0
            ),
            bypass_hours=int(t["fields"]["Reservation Hours to Skip Recert"]),
            bypass_tools=set(
                t["fields"]["Related Tools for Recert"] + t["fields"]["Tool Code"]
            ),
            bypass_cutoff=cutoff,
        )
        if not cfg.expiration:
            continue
        tool_configs[cfg.tool] = cfg
    return tool_configs


def get_pending_recertifications() -> (
    Iterator[tuple[NeonID, ToolCode, datetime.datetime, datetime.datetime, RecordID]]
):
    """Get all pending recerts"""
    for rec in get_all_records("people", "recertification"):
        yield (
            rec["fields"]["Neon ID"],
            rec["fields"]["Tool Code"].strip(),
            dateparser.parse(rec["fields"]["Instruction Deadline"]),
            dateparser.parse(rec["fields"]["Reservation Deadline"]),
            rec["id"],
        )


def insert_pending_recertification(
    neon_id: str,
    tool_code: str,
    inst_deadline: datetime.datetime,
    res_deadline: datetime.datetime,
):
    """Inserts a new recertification into the pending recertifications table"""
    return insert_records(
        [
            {
                "Neon ID": neon_id,
                "Tool Code": tool_code,
                "Instruction Deadline": inst_deadline.isoformat(),
                "Reservation Deadline": res_deadline.isoformat(),
            }
        ],
        "people",
        "recertification",
    )


def update_pending_recertification(rec: str, inst_deadline, res_deadline):
    """Update pending recertification"""
    _, content = update_record(
        {
            "Instruction Deadline": inst_deadline.isoformat(),
            "Reservation Deadline": res_deadline.isoformat(),
        },
        "people",
        "recertification",
        rec,
    )
    return content


def remove_pending_recertification(rec: str):
    """Deletes a recertification by record ID"""
    return delete_record("people", "recertification", rec)


def get_reports_for_tool(airtable_id, back_days=90):
    """Fetches all tool reports tagged with a particular tool record in Airtable"""
    for r in get_all_records_after(
        "tools_and_equipment",
        "tool_reports",
        tznow() - datetime.timedelta(days=back_days),
    ):
        if airtable_id not in r["fields"].get("Equipment Record", []):
            continue
        yield {
            "t": safe_parse_datetime(r["fields"].get("Created")),
            "date": r["fields"].get("Created"),
            "name": r["fields"].get("Name"),
            "state": r["fields"].get("Current equipment status"),
            "email": r["fields"].get("Email"),
            "message": r["fields"].get("What's the problem?"),
            "summary": r["fields"].get("Actions taken"),
            "asana": r["fields"].get("Asana Link"),
        }


def get_areas():
    """Get all areas in the Area table"""
    return get_all_records("tools_and_equipment", "areas")


def get_tool_id_and_name(tool_code: str):
    """Fetches the name and ID of a tool in Airtable, based on its tool code"""
    for t in get_tools():
        if (
            t["fields"].get("Tool Code", "").strip().lower()
            == tool_code.strip().lower()
        ):
            return (t["id"], t["fields"].get("Tool Name"))
    return None, None


@lru_cache(maxsize=1)
def get_clearance_to_tool_map():
    """Returns a mapping of clearance codes (e.g. MWB) to individual tool codes"""
    airtable_clearances = get_all_records("tools_and_equipment", "clearances")
    airtable_tools = get_all_records("tools_and_equipment", "tools")
    tool_code_by_id = {t["id"]: t["fields"]["Tool Code"] for t in airtable_tools}
    clearance_to_tool = {}
    for c in airtable_clearances:
        cc = c["fields"].get("Clearance Code")
        if cc is None:
            log.debug(f"Skipping (missing clearance code): '{c['fields'].get('Name')}'")
            continue
        ctt = set()
        for tool_id in c["fields"].get("Tool Records", []):
            ct = tool_code_by_id.get(tool_id)
            if ct is not None:
                ctt.add(ct)
        clearance_to_tool[cc] = ctt
    return clearance_to_tool


def insert_signin(evt):
    """Insert sign-in event into Airtable"""
    return insert_records([evt], "people", "sign_ins")


def get_all_announcements():
    """Fetches and returns all announcements in the table"""
    return list(get_all_records("people", "sign_in_announcements"))


def get_all_tech_bios():
    """Fetches and returns all tech bios and photos from airtable/nocodb"""
    return list(get_all_records("people", "volunteers_staff"))


def get_signins_between(start, end) -> Iterator[SignInEvent | None]:
    """Fetches all sign-in data between two dates; or after `start` if `end` is None"""
    if not end:
        for rec in get_all_records_after("people", "sign_ins", start):
            yield SignInEvent.from_airtable(rec)
    else:
        for rec in get_all_records_between("people", "sign_ins", start, end):
            yield SignInEvent.from_airtable(rec)


def insert_simple_survey_response(announcement_id, email, neon_id, response):
    """Insert a survey response from the welcome page into Airtable"""
    return insert_records(
        [
            {
                "Announcement": [announcement_id],
                "Email": email,
                "Neon ID": neon_id,
                "Response": response,
            }
        ],
        "people",
        "sign_in_survey_responses",
    )


def get_policy_sections():
    """Gets all sections of policy that require enforcement"""
    return get_all_records("policy_enforcement", "sections")


def get_policy_violations():
    """Returns all policy violations"""
    rows = get_all_records("policy_enforcement", "violations")
    return [v for v in rows if v["fields"].get("Onset")]


def open_violation(  # pylint: disable=too-many-arguments
    reporter, suspect, sections, evidence, onset, fee, notes
):
    """Opens a new violation with a fee schedule"""
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


def get_policy_fees():
    """Returns all fees in the table"""
    rows = get_all_records("policy_enforcement", "fees")
    return [f for f in rows if f["fields"].get("Created")]


def create_fees(fees, batch_size=10):
    """Create fees for each violation and fee amount in the map"""
    data = [{"Created": t, "Violation": [vid], "Amount": amt} for vid, amt, t in fees]
    for i in range(0, len(data), batch_size):
        batch = data[i : i + batch_size]
        rep = insert_records(batch, "policy_enforcement", "fees")
    return rep


def create_coupon(code, amount, use_by, expires):
    """Create fees for each violation and fee amount in the map"""
    data = [
        {
            "Code": code,
            "Amount": amount,
            "Use By": use_by.strftime("%Y-%m-%d"),
            "Created": tznow().isoformat(),
            "Expires": expires.strftime("%Y-%m-%d"),
        }
    ]
    return insert_records(data, "class_automation", "discounts")


def get_num_valid_unassigned_coupons(use_by):
    """Counts the number of coupons that can be assigned, with
    a 'Use By' date of at least `use_by`."""
    num = 0
    for row in get_all_records_after(
        "class_automation", "discounts", use_by, field="Use By"
    ):
        if not row["fields"].get("Assigned"):
            num += 1
    return num


def get_next_available_coupon(use_by=None):
    """Gets all logged targets that were sent after a specific date,
    including their date of ontification"""
    if not use_by:
        use_by = tznow() + datetime.timedelta(days=30)
    for row in get_all_records_after(
        "class_automation", "discounts", use_by, field="Use By"
    ):
        if row["fields"].get("Assigned"):
            continue
        return row


def mark_coupon_assigned(rec, assignee):
    """Marks the coupon as assigned to a particular assignee"""
    _, content = update_record(
        {
            "Assigned": tznow().isoformat(),
            "Assignee": assignee,
        },
        "class_automation",
        "discounts",
        rec,
    )
    return content


def pay_fee(fee_id):
    """Mark fee as paid"""
    raise NotImplementedError()


def _day_trunc(d):
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def get_instructor_availability(inst_rec):
    """Fetches all rows from Availability airtable matching `inst` as instructor"""
    for row in get_all_records("class_automation", "availability"):
        row_inst = (row["fields"]["Instructor (from Instructor)"] or [""])[0].lower()
        if inst_rec in row_inst:
            yield row


MAX_EXPANSION = 1000


def expand_instructor_availability(rows, t0, t1):
    """Given the `Availability` Airtable as `rows` and interval `t0` to
    `t1`, return all events within the interval
    as (airtable_id, start_time, end_time) tuples.

    Note that this doesn't deduplicate or merge overlapping availabilities.
    """
    for row in rows:
        start0, end0 = safe_parse_datetime(row["fields"]["Start"]), safe_parse_datetime(
            row["fields"]["End"]
        )
        rr = (row["fields"].get("Recurrence") or "").replace("RRULE:", "")
        try:
            rr = rrulestr(rr, dtstart=start0) if rr != "" else None
        except ValueError as e:
            log.warning("Failed to parse rrule str: %s, %s", rr, str(e))
            rr = None

        if not rr:  # Empty or malformed
            if (
                t0 <= start0 <= t1 or t0 <= end0 <= t1 or (start0 <= t0 and t1 <= end0)
            ):  # Only yield if event overlaps the interval
                yield row["id"], max(start0, t0), min(end0, t1)
        else:
            duration = end0 - start0
            for start in rr.xafter(
                t0 - datetime.timedelta(hours=24), count=MAX_EXPANSION, inc=True
            ):
                end = start + duration
                if start > t1:  # Stop iterating once we've slid past the interval
                    break
                if end < t0:  # Advance until we get dates within the interval
                    continue
                yield row["id"], max(start, t0), min(end, t1)


def add_availability(inst_id, start, end, recurrence=""):
    """Adds an optionally-recurring availability row to the Availability airtable"""
    return insert_records(
        [
            {
                "Instructor": [inst_id],
                "Start": start.isoformat(),
                "End": end.isoformat(),
                "Recurrence": recurrence,
            }
        ],
        "class_automation",
        "availability",
        link_fields=["Instructor"],
    )


def update_availability(
    rec, inst_id, start, end, recurrence
):  # pylint: disable=too-many-arguments
    """Updates a specific availability record"""
    return update_record(
        {
            "Instructor": [inst_id],
            "Start": start.isoformat(),
            "End": end.isoformat(),
            "Recurrence": recurrence,
        },
        "class_automation",
        "availability",
        rec,
    )


def delete_availability(rec):
    """Removes an Availability record"""
    return delete_record("class_automation", "availability", rec)


def get_forecast_overrides(include_pii) -> Iterator[tuple[str, ForecastOverride]]:
    """Gets all overrides for the shop tech shift forecast"""
    for r in get_all_records("people", "shop_tech_forecast_overrides"):
        if r["fields"].get("Shift Start", None) is None:
            continue
        d = safe_parse_datetime(r["fields"]["Shift Start"])
        ap = "AM" if d.hour < 12 else "PM"
        techs = r["fields"].get("Override", "").split("\n")
        last_modified = (
            f"{r['fields'].get('Last Modified By', 'Unknown')} "
            f"on {r['fields']['Last Modified']}"
        )

        if not include_pii:  # "First name" only if no PII allowed
            techs = [t.split(" ")[0] for t in techs]
            last_modified = r["fields"]["Last Modified"]
        yield f"{d.strftime('%Y-%m-%d')} {ap}", (
            r["id"],
            techs if techs != [""] else [],
            last_modified,
        )


def delete_forecast_override(rec):
    """Deletes a shift override by its id"""
    _, content = delete_record("people", "shop_tech_forecast_overrides", rec)
    return content


def set_forecast_override(  # pylint: disable=too-many-arguments
    rec, date, ap, techs, editor_email, editor_name
):
    """Upserts a shop tech shift override"""
    ap = ap.lower()
    date = safe_parse_datetime(date).replace(
        hour=10 if ap.lower() == "am" else 16, minute=0, second=0, tzinfo=tz
    )
    data = {
        "Shift Start": date.isoformat(),
        "Override": "\n".join(techs),
        "Last Modified By": f"{editor_name} ({editor_email})",
    }
    if rec is not None:
        return update_record(data, "people", "shop_tech_forecast_overrides", rec)
    return insert_records([data], "people", "shop_tech_forecast_overrides")


def insert_quiz_result(
    submitted: datetime.datetime,
    email: str,
    tool_codes: list[str],
    data: dict,
    points_scored: int,
    points_to_pass: int,
):  # pylint: disable=too-many-arguments
    """Insert sign-in event into Airtable"""
    return insert_records(
        [
            {
                "Submitted": submitted.astimezone(tz).isoformat(),
                "Email": email,
                "Tool Codes": ",".join(tool_codes),
                "Data": json.dumps(data),
                "Points Scored": points_scored,
                "Points to Pass": points_to_pass,
            },
        ],
        "class_automation",
        "quiz_results",
    )


class AirtableCache(WarmDict):
    """Prefetches airtable data for faster lookup"""

    NAME = "airtable"
    REFRESH_PD_SEC = datetime.timedelta(hours=24).total_seconds()
    RETRY_PD_SEC = datetime.timedelta(minutes=5).total_seconds()

    def refresh(self):
        """Refresh values; called every REFRESH_PD"""
        self.log.info("Beginning AirtableCache refresh")
        self["announcements"] = get_all_announcements()
        self["violations"] = get_policy_violations()
        self.log.info(
            f"AirtableCache refresh complete; {len(self['announcements'])} announcements, "
            f"{len(self['violations'])} violations loaded. "
            f"Next update in {self.REFRESH_PD_SEC} seconds"
        )

    def violations_for(self, account_id):
        """Check member for storage violations"""
        for pv in self["violations"]:
            if str(pv["fields"].get("Neon ID")) != str(account_id) or pv["fields"].get(
                "Closure"
            ):
                continue
            yield pv

    def announcements_after(self, d, roles, clearances):
        """Gets all announcements, excluding those before `d`"""
        now = tznow()

        # Neon clearance data is of the format `<TOOL_CODE>: <TOOL_NAME>`.
        # announcements_after expects a set of tool names.
        log.info(f"Clearances: {clearances}")
        clearances = [n.split(":")[1].strip() for n in clearances if ":" in n]

        for row in self["announcements"]:
            adate = safe_parse_datetime(row["fields"].get("Published", "2024-01-01"))
            if adate <= d or adate > now:
                continue

            tools = set(row["fields"].get("Tool Name (from Tool Codes)", []))
            if len(tools) > 0:
                cleared_for_tool = False
                for c in clearances:
                    if c in tools:
                        cleared_for_tool = True
                        break
                if not cleared_for_tool:
                    continue

            for r in row["fields"].get("Roles", []):
                if r in roles:
                    row["fields"]["rec_id"] = row["id"]
                    yield row["fields"]
                    break


cache = AirtableCache()
