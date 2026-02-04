"""Airtable integration (classes, tool state etc)"""  # pylint: disable=too-many-lines

import datetime
import json
import logging
import re
import traceback
import urllib.parse
from collections import defaultdict
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Iterator

from dateutil import parser as dateparser

from protohaven_api.config import get_config, safe_parse_datetime, tz, tznow
from protohaven_api.integrations.airtable_base import (
    _idref,
    _refid,
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

Email = str
NeonID = str
ToolCode = str
AreaID = str
InstructorID = str  # Currently, the email address listed in the capabilities doc
RecordID = str
ForecastOverride = tuple[str, list[str], str]
Interval = tuple[datetime.datetime, datetime.datetime]


@dataclass
class Class:  # pylint: disable=too-many-instance-attributes
    """Represents a class template"""

    class_id: RecordID
    name: str
    hours: list[int]
    capacity: int
    price: int
    period: datetime.timedelta
    approved: bool
    schedulable: bool
    approved_instructors: list[InstructorID]
    areas: list[AreaID]
    image_link: str
    clearances: list[ToolCode]

    @classmethod
    def resolve_hours(cls, hours, days) -> list[float]:
        """Compatibility layer to allow for rollback to previous data structure"""
        try:
            if not days:
                return [float(s) for s in str(hours).split(",") or []]
            return [float(hours)] * int(days)
        except ValueError:
            traceback.print_exc()
            return [0.0]

    @classmethod
    def from_template(cls, row):
        """Converts an airtable template row into Class"""
        f = row["fields"]
        return cls(
            class_id=str(row["id"]),
            name=f.get("Name"),
            hours=cls.resolve_hours(f.get("Hours"), f.get("Days")),
            capacity=int(f.get("Capacity") or 0),
            price=int(f.get("Price") or 0),
            period=datetime.timedelta(days=int(f.get("Period") or 0)),
            areas=f.get("Name (from Area)") or [],
            schedulable=bool(f.get("Schedulable")),
            approved=bool(f.get("Approved")),
            image_link=f.get("Image Link"),
            clearances=f.get("Form Name (from Clearance)") or [],
            approved_instructors=f.get("Email (from Instructor Capabilities)") or [],
        )

    @property
    def days(self):
        """Compute number of days of the class from the hours data"""
        return len(self.hours)

    def as_response(self):
        """Return a dict that can be used as a flask response, including prefill"""
        return {
            **asdict(self),
            "period": self.period.total_seconds() / (24 * 3600),
        }


@dataclass
class ScheduledClass:  # pylint: disable=too-many-instance-attributes
    """Represents a class template with scheduling information applied"""

    schedule_id: RecordID
    class_id: RecordID
    neon_id: str  # Neon Event ID
    name: str
    hours: list[int]
    period: datetime.timedelta
    capacity: int
    supply_state: str
    areas: list[str]
    confirmed: datetime.datetime
    rejected: datetime.datetime
    image_link: str
    clearances: list[str]
    price: int
    instructor_name: str
    instructor_email: InstructorID
    sessions: list[Interval]
    volunteer: bool
    description: dict[str, str]

    @classmethod
    def resolve_starts(cls, sessions, start_time, days, days_between):
        """Compatibility for old table data"""
        if sessions:
            return [safe_parse_datetime(d) for d in sessions.split(",")]
        d = safe_parse_datetime(start_time)
        return [
            d + datetime.timedelta(days=i * int(days_between)) for i in range(int(days))
        ]

    @classmethod
    def from_schedule(cls, row):
        """Converts airtable schedule row into ScheduledClass"""
        f = row["fields"]
        hours = Class.resolve_hours(
            _unwrap(f, "Hours (from Class)"),
            _unwrap(f, "Days (from Class)"),
        )
        if not hours:
            raise RuntimeError("Class template data for session has no hours listed")

        starts = cls.resolve_starts(
            f.get("Sessions") or None,
            f.get("Start Time") or None,
            _unwrap(f, "Days (from Class)"),
            _unwrap(f, "Days Between Sessions (from Class)"),
        )
        if len(hours) < len(
            starts
        ):  # We need consistent lengths for pairing up data elsewhere
            hours += [hours[0]] * (len(starts) - len(hours))

        sessions = [
            (d, d + datetime.timedelta(hours=hours[i])) for i, d in enumerate(starts)
        ]
        class_ids = [None]
        if "Class" in f.keys():
            class_ids = _idref(row, "Class")
        return cls(
            schedule_id=str(row["id"]),
            class_id=str(class_ids[0]),
            neon_id=f.get("Neon ID") or None,
            name=_unwrap(f, "Name (from Class)"),
            hours=hours,
            period=datetime.timedelta(
                days=int(_unwrap(f, "Period (from Class)") or 0),
            ),
            capacity=int(_unwrap(f, "Capacity (from Class)") or 0),
            supply_state=f.get("Supply State") or "Unknown supply state",
            areas=f.get("Name (from Area) (from Class)") or [],
            confirmed=(
                safe_parse_datetime(f.get("Confirmed")) if f.get("Confirmed") else None
            ),
            rejected=(
                safe_parse_datetime(f.get("Rejected")) if f.get("Rejected") else None
            ),
            image_link=_unwrap(f, "Image Link (from Class)"),
            clearances=f.get("Form Name (from Clearance) (from Class)") or [],
            price=int(_unwrap(f, "Price (from Class)") or 0),
            instructor_email=(f.get("Email") or "").strip().lower(),
            instructor_name=f.get("Instructor") or "",
            sessions=sessions,
            volunteer=f.get("Volunteer") or False,
            description={
                k: _unwrap(f, k + " (from Class)") or ""
                for k in (
                    "Short Description",
                    "What you Will Create",
                    "What to Bring/Wear",
                    "Clearances Earned",
                    "Age Requirement",
                )
            },
        )

    def prefill_form(self, pass_emails: list[str], session_idx: int = 0):
        """Return prefilled instructor log submission form"""
        individual = get_instructor_log_tool_codes()
        clearance_codes = []
        tool_codes = []
        for c in self.clearances:
            if c in individual:
                tool_codes.append(c)
            else:
                clearance_codes.append(c)

        # Get form configuration
        form_base = get_config("forms/instructor_log/base_url")
        form_keys = get_config("forms/instructor_log/keys")
        form_values = get_config("forms/instructor_log/values")

        start_yyyy_mm_dd = self.start_time.strftime("%Y-%m-%d")
        result = f"{form_base}?usp=pp_url"
        result += (
            f"&{form_keys['instructor']}={urllib.parse.quote(self.instructor_name)}"
        )
        result += f"&{form_keys['date']}={start_yyyy_mm_dd}"
        result += f"&{form_keys['hours']}={self.hours[session_idx]}"
        result += f"&{form_keys['class_name']}={urllib.parse.quote(self.name)}"
        if self.volunteer:
            result += f"&{form_keys['volunteer']}={form_values['volunteer_yes']}"
        result += f"&{form_keys['session_type']}={form_values['single_session']}"
        result += (
            f"&{form_keys['pass_emails']}={urllib.parse.quote(', '.join(pass_emails))}"
        )
        for cc in clearance_codes:
            result += f"&{form_keys['clearance_codes']}={cc}"
        tool_usage_value = (
            form_values["tool_usage_yes"]
            if len(tool_codes) > 0
            else form_values["tool_usage_no"]
        )
        result += f"&{form_keys['tool_usage']}={tool_usage_value}"
        result += f"&{form_keys['event_id']}={self.neon_id or 'UNKNOWN'}"
        for tc in tool_codes:
            result += f"&{form_keys['tool_codes']}={tc}"
        return result

    @property
    def start_time(self):
        """Return the start time of the class"""
        return min(s[0] for s in self.sessions)

    @property
    def end_time(self):
        """Return the very last point in time for the class (end of the last session)"""
        return max(s[1] for s in self.sessions)

    @property
    def days(self):
        """Returns days calculated from hours data"""
        return len(self.hours)

    def as_response(self, pass_emails=None):
        """Return a dict that can be used as a flask response, including prefill"""
        if not pass_emails:
            pass_emails = ["ATTENDEE_NAMES"]
        return {
            **asdict(self),
            "prefill": self.prefill_form(pass_emails),
            "period": self.period.total_seconds() / (24 * 3600),
        }


def _unwrap(row, field):
    """Lookup fields in Airtable vs Nocodb may be differently configured
    (e.g. many-to-many vs one-to-many). This causes a difference in
    data type that requires "unwrapping" many-to-many fields that are
    used as one-to-many, as in the Schedule table of airtable."""
    v = row.get(field)
    if isinstance(v, list):
        return v[0]
    return v


def get_class_automation_schedule(include_rejected=True, raw=True):
    """Grab the current automated class schedule"""
    for row in get_all_records("class_automation", "schedule"):
        if not row["fields"].get("Rejected") or include_rejected:
            yield (row if raw else ScheduledClass.from_schedule(row))


def get_scheduled_class(rec, raw=True):
    """Get the specific scheduled class row by reference"""
    result = get_record("class_automation", "schedule", rec)
    if result and not raw:
        return ScheduledClass.from_schedule(result)
    return result


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
        f = row["fields"]
        if f.get("Instructor").lower() != name.lower():
            continue
        result = {
            "id": str(row["id"]),
            "w9": f.get("W9 Form"),
            "direct_deposit": f.get("Direct Deposit Info"),
            "bio": f.get("Bio"),
            "classes": [],
            "profile_pic": None,
        }
        log.info(str(row))
        if "Class" in f.keys():
            class_ids = _idref(row, "Class")
            result["classes"] = {
                str(c[0]): c[1] for c in zip(class_ids, f["Name (from Class)"])
            }

        img = (f.get("Profile Pic") or [{"url": None}])[0]
        if img:
            result["profile_pic"] = (
                img.get("url")
                or f"{get_config('nocodb/requests/url')}/{img.get('path')}"
            )
        return result


def fetch_instructor_teachable_classes():
    """Fetch teachable classes from airtable"""
    instructor_caps = defaultdict(list)
    for row in get_all_records("class_automation", "capabilities"):
        if not row["fields"].get("Instructor"):
            continue
        inst = row["fields"]["Instructor"].strip().lower()
        if "Class" in row["fields"].keys():
            instructor_caps[inst] += _idref(row, "Class")
    return instructor_caps


def get_all_class_templates(raw=True):
    """Get all class templates"""
    result = get_all_records("class_automation", "classes")
    if raw:
        yield from result
    for row in result:
        yield Class.from_template(row)


def get_class_template(cls_id: RecordID) -> Class:
    """Fetches a class template object from Airtable"""
    for row in get_all_class_templates():
        log.info(f"{row['id']} vs {cls_id}")
        if str(row["id"]) == str(cls_id):
            return Class.from_template(row)
    return None


def append_classes_to_schedule(payload):
    """Takes {Instructor, Email, Start Time, [Class]} and adds to schedule"""
    assert isinstance(payload, list)
    for c in payload:  # Ensure correct format for linking
        c["Class"] = [_refid(i) for i in c["Class"]]
    return insert_records(payload, "class_automation", "schedule")


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


def respond_class_automation_schedule(eid: RecordID, pub: bool) -> ScheduledClass:
    """Confirm or unconfirm a row in the Schedule table of class automation"""
    t = tznow().isoformat()
    data = {
        "Confirmed": t if pub is True else "",
        "Rejected": t if pub is False else "",
    }
    status, result = update_record(data, "class_automation", "schedule", eid)
    if status != 200:
        raise RuntimeError(f"Error updating class schedule state for {eid}: {result}")
    return ScheduledClass.from_schedule(result)


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


def mark_schedule_supply_request(eid: RecordID, state) -> ScheduledClass:
    """Mark a Scheduled class as needing supplies or fully supplied"""
    status, result = update_record(
        {"Supply State": state},
        "class_automation",
        "schedule",
        eid,
    )
    if status != 200:
        raise RuntimeError(f"Error setting supply state for {eid}: {result}")
    return ScheduledClass.from_schedule(result)


def mark_schedule_volunteer(eid: RecordID, volunteer: bool) -> ScheduledClass:
    """Mark volunteership or desire to run the Scheduled class for pay"""
    status, result = update_record(
        {"Volunteer": volunteer}, "class_automation", "schedule", eid
    )
    if status != 200:
        raise RuntimeError(f"Error setting volunteer status for {eid}: {result}")
    return ScheduledClass.from_schedule(result)


def get_tools():
    """Get all tools in the tool DB"""
    return get_all_records("tools_and_equipment", "tools")


@dataclass
class RecertConfig:  # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """All metadata used to inform whether or not a member's clearance should undergo
    recertification, and how the recert happens (e.g. quiz vs instruction)"""

    tool: ToolCode
    tool_name: str
    quiz_url: str
    expiration: datetime.timedelta
    bypass_hours: int
    bypass_tools: set[ToolCode]
    bypass_cutoff: datetime.timedelta
    humanized: str

    def as_dict(self) -> dict[str, Any]:
        """Convert the instance to a dictionary for serialization."""
        return {
            "tool": self.tool,
            "tool_name": self.tool_name,
            "quiz_url": self.quiz_url,
            "expiration_sec": self.expiration.total_seconds(),
            "bypass_hours": self.bypass_hours,
            "bypass_tools": list(self.bypass_tools),
            "bypass_cutoff_sec": self.bypass_cutoff.total_seconds(),
            "humanized": self.humanized,
        }


def get_tool_recert_configs_by_code() -> dict[ToolCode, RecertConfig]:
    """Returns formatted recertification configs, keyed by tool code"""
    tool_configs = {}
    cutoff = datetime.timedelta(
        days=int(get_config("general/recertification/bypass_hours_window_days"))
    )
    for t in get_tools():
        f = t["fields"]
        if not f.get("Tool Code"):
            continue
        cfg = RecertConfig(
            tool=str(f.get("Tool Code")),
            tool_name=f.get("Tool Name") or "UNKNOWN",
            quiz_url=f.get("Recert Quiz"),
            expiration=datetime.timedelta(days=f.get("Days until Recert Needed") or 0),
            bypass_hours=int(f.get("Reservation Hours to Skip Recert") or 0),
            bypass_tools=set(
                (f.get("Tool Code (from Related Tools for Recert)") or [])
                + [f.get("Tool Code")]
            ),
            bypass_cutoff=cutoff,
            humanized=f.get("Recertification"),
        )
        if not cfg.tool or not cfg.expiration:
            continue
        tool_configs[cfg.tool] = cfg
    return tool_configs


@dataclass
class PendingRecert:
    """Represents a pending recertification in the Recertifications table in Airtable"""

    neon_id: NeonID
    tool_code: ToolCode
    inst_deadline: datetime.datetime
    res_deadline: datetime.datetime
    notified: datetime.datetime
    suspended: bool
    rec_id: RecordID | None


def get_pending_recertifications() -> Iterator[PendingRecert]:
    """Get all pending recerts"""
    for rec in get_all_records("people", "recertification"):
        if not rec["fields"].get("Tool Code"):
            continue
        yield PendingRecert(
            neon_id=str(rec["fields"]["Neon ID"]),
            tool_code=str(rec["fields"]["Tool Code"]).strip(),
            inst_deadline=dateparser.parse(
                rec["fields"]["Instruction Deadline"]
            ).astimezone(tz),
            res_deadline=dateparser.parse(
                rec["fields"]["Reservation Deadline"]
            ).astimezone(tz),
            notified=(
                dateparser.parse(rec["fields"].get("Notified")).astimezone(tz)
                if rec["fields"].get("Notified")
                else None
            ),
            suspended=bool(rec["fields"].get("Suspended")),
            rec_id=rec["id"],
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
                "Instruction Deadline": inst_deadline.strftime("%Y-%m-%d"),
                "Reservation Deadline": res_deadline.strftime("%Y-%m-%d"),
            }
        ],
        "people",
        "recertification",
    )


def update_pending_recertification(
    rec: str, inst_deadline=None, res_deadline=None, suspended=None
):
    """Update pending recertification"""
    data = {}
    if inst_deadline:
        data["Instruction Deadline"] = inst_deadline.strftime("%Y-%m-%d")
    if res_deadline:
        data["Reservation Deadline"] = res_deadline.strftime("%Y-%m-%d")
    if suspended is not None:
        data["Suspended"] = suspended

    _, content = update_record(
        data,
        "people",
        "recertification",
        rec,
    )
    return content


def remove_pending_recertification(rec: str):
    """Deletes a recertification by record ID"""
    return delete_record("people", "recertification", rec)


def log_recerts_notified(recerts):
    """Update recert log record with the current timestamp"""
    for recert in recerts:
        update_record(
            {"Notified": tznow().isoformat()},
            "people",
            "recertification",
            recert,
        )


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
                "Relevant Sections": [_refid(section_map[int(s)]) for s in sections],
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
    data = [
        {"Created": t, "Violation": [_refid(vid)], "Amount": amt}
        for vid, amt, t in fees
    ]
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


def get_latest_passing_quizzes_by_email_and_tool(
    after: datetime.datetime | None = None,
) -> dict[tuple[NeonID, ToolCode], datetime.datetime]:
    """Returns a dict of the most recent date a quiz was passed for a specific email and tool"""
    result: dict[tuple[NeonID, ToolCode], datetime.datetime] = {}
    for row in get_all_records("class_automation", "quiz_results"):
        f = row["fields"]
        log.info(f"row {f}")
        if int(f.get("Points Scored") or 0) < int(f.get("Points to Pass") or 999):
            log.debug("Not passing; ignoring")
            continue

        d = safe_parse_datetime(f["Submitted"])
        if after and d < after:
            continue
        for tc in f["Tool Codes"].split(","):
            k = (f["Email"].strip().lower(), tc.strip().upper())
            result[k] = d if k not in result else max(d, result[k])
    return result


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
