"""Commands related to developing on the API"""

import logging
import pickle
import random
import string
from collections import defaultdict

from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import get_config  # pylint: disable=import-error
from protohaven_api.integrations import (  # pylint: disable=import-error
    airtable,
    neon,
    neon_base,
)

log = logging.getLogger("cli.dev")


def random_fname(*args):  # pylint: disable=unused-argument
    """Returns a random first name"""
    first_names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Hank"]
    return random.choice(first_names)


def random_lname(*args):  # pylint: disable=unused-argument
    """Returns a random last name"""
    last_names = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
    ]
    return random.choice(last_names)


def random_id(*args):  # pylint: disable=unused-argument
    """Generate a random 4-digit integer."""
    return str(random.randint(1000, 9999))


def random_name(*args):  # pylint: disable=unused-argument
    """Returns a random 'full' name"""
    return f"{random_fname()} {random_lname()}"


def random_email(*args):  # pylint: disable=unused-argument
    """Generate a random email address."""

    domains = ["example.com", "test.com", "demo.com", "sample.com"]
    username = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    domain = random.choice(domains)
    return f"{username}@{domain}"


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for development"""

    def _sanitize_account(self, acc):
        """Remove sensitive demographic, financial, location and non-email contact information"""
        acc["accountCustomFields"] = [
            a
            for a in acc.get("accountCustomFields", [])
            if a.get("name")
            not in (
                "Accessibility Demographics",
                "Identity Demographics",
                "Race/Ethnicity",
                "Age",
                "Proof of Income",
                "Income Based Rate",
            )
        ]
        if acc.get("primaryContact"):
            acc["primaryContact"].update(
                {"addresses": [], "phone1": "", "phone2": "", "phone3": ""}
            )
        acc["generosityIndicator"] = None
        return acc

    def _fetch_neon_events(self, after):
        log.info("Fetching events from neon...")
        events = {e["id"]: e for e in neon.fetch_events(after=dateparser.parse(after))}

        log.info(
            f"Fetching and sanitizing event attendees for {len(events)} event(s)..."
        )
        attendees = defaultdict(list)
        for e in events.keys():
            log.info(f"- Event #{e}")
            for a in neon.fetch_attendees(e):
                attendees[e].append(
                    {
                        **{
                            k: a[k]
                            for k in (
                                "registrationStatus",
                                "registrationDate",
                                "eventName",
                                "registrationId",
                                "ticketName",
                            )
                        },
                        "attendeeId": random_id(),
                        "accountId": random_id(),
                        "firstName": random_fname(),
                        "lastName": random_lname(),
                        "registrantAccountId": random_id(),
                        "email": random_email(),
                    }
                )
        return events, attendees

    def _fetch_airtable(self):
        log.info("Fetching airtable data...")
        tables = defaultdict(lambda: defaultdict(list))
        # Every field of every table must be present here - we make the explicit choice to expose
        # or sanitize/obfuscate individual fields in the mock data.
        table_sanitization = {
            "tools_and_equipment": {
                "areas": {
                    "Name": None,
                    "Tool Records": None,
                    "Clearances": None,
                    "Color": None,
                },
                "tools": {
                    "Tool Name": None,
                    "Shop Area": None,
                    "Make and Model": None,
                    "Clearance Required": None,
                    "Current Status": None,
                    "Status Message": None,
                    "Purchase Requests": None,
                    "Tool Reports": None,
                    "BookedResourceId": None,
                    "Wiki URL": None,
                    "Image": None,
                    "Show In Tool List": None,
                    "Show clearance button": None,
                    "Tool Code": None,
                    "Clearance URL": None,
                    "Reservable": None,
                    "Status Report": None,
                    "Reserve": None,
                    "Docs": None,
                    "History": None,
                    "Clearance": None,
                    "Clearance Code (from Clearance Required)": None,
                    "Name (from Shop Area)": None,
                    "Status last modified": None,
                    "Recurring Tasks": None,
                    "Consumables": None,
                    "Recurring Tasks copy": None,
                },
                "clearances": {
                    "Name": None,
                    "Status": None,
                    "Clearance Code": None,
                    "Area": None,
                    "Tool Records": None,
                },
                "recurring_tasks": {
                    "Id": None,
                    "Last Scheduled": None,
                    "Task Name": None,
                    "Task Detail": None,
                    "Tool/Area": None,
                    "Frequency": None,
                    "Managed By": random_name,
                    "Asana Section": None,
                    "Skill Level": None,
                    "Next Schedule Date": None,
                    "Rendered Tool/Area": None,
                },
                "tool_reports": {
                    "Name": random_name,
                    "Email": random_email,
                    "Request or action": None,
                    "What's the problem?": None,
                    "Actions taken": None,
                    "Current equipment status": None,
                    "Equipment Record": None,
                    "Created": None,
                    "Primary": None,
                    "Status": None,
                    "Rendered Tool Name": None,
                    "Create Asana Task": None,
                    "Asana Link": None,
                    "Urgent": None,
                    "Confirmation of physical tag": None,
                    "Images of problem (optional)": None,
                },
            },
            "class_automation": {
                "clearance_codes": {
                    "Form Name": None,
                    "Code": None,
                    "Class Templates": None,
                    "Individual": None,
                    "Instructor Capabilities": None,
                },
                "classes": {
                    "Name": None,
                    "Capacity": None,
                    "ID": None,
                    "Hours": None,
                    "Days": None,
                    "What to Bring/Wear": None,
                    "What you Will Create": None,
                    "Age Requirement": None,
                    "Short Description": None,
                    "Clearance": None,
                    "Period": None,
                    "Instructor Cost": None,
                    "Price": None,
                    "Form Name (from Clearance)": None,
                    "Description": None,
                    "Clearances Earned": None,
                    "Instructor Capabilities": None,
                    "Confirmations": None,
                    "Schedulable": None,
                    "Area": None,
                    "Supply Cost": None,
                    "Approved": None,
                    "Image Link": None,
                    "Name (from Area)": None,
                    "Price Override": None,
                    "Prerequisites": None,
                },
                "capabilities": {
                    "ID": None,
                    "Instructor": random_name,
                    "Class": None,
                    "Email": random_email,
                    "Can you teach any other classes not listed here?": None,
                    "W9 Form": (lambda _: ["https://link_to_w9.com"]),
                    "Direct Deposit Info": (
                        lambda _: ["https://link_to_direct_deposit.com"]
                    ),
                    "Profile Pic": (lambda _: "https://example.com"),
                    "Bio": (lambda _: "https://example.com"),
                    "Portfolio": (lambda _: "https://example.com"),
                    "Active": None,
                    "Availability": None,
                    "Position": None,
                    "Name (from Class)": None,
                    "Private Instruction": None,
                },
                "email_log": {
                    "ID": None,
                    "To": random_email,
                    "Subject": (lambda _: "Some random email"),
                    "Status": None,
                    "Neon ID": random_id,
                    "Created": None,
                },
                "schedule": {
                    "ID": None,
                    "Class": None,
                    "Start Time": None,
                    "Capacity (from Class)": None,
                    "Description (from Class)": None,
                    "Name (from Class)": None,
                    "Email": random_email,
                    "Instructor": random_name,
                    "Confirmed": None,
                    "Price (from Class)": None,
                    "Hours (from Class)": None,
                    "Days (from Class)": None,
                    "Age Requirement (from Class)": None,
                    "Clearances Earned (from Class)": None,
                    "What to Bring/Wear (from Class)": None,
                    "Short Description (from Class)": None,
                    "Neon ID": None,
                    "Supply State": None,
                    "Name (from Area) (from Class)": None,
                    "Image Link (from Class)": None,
                    "Period (from Class)": None,
                    "Supply Cost (from Class)": None,
                    "Form Name (from Clearance) (from Class)": None,
                    "What you Will Create (from Class)": None,
                    "Rejected": None,
                    "Volunteer": None,
                    "Prerequisites (from Class)": None,
                },
                "boilerplate": {"Name": None, "Notes": None},
                "availability": {
                    "Instructor": (lambda _: [random_id()]),
                    "Start": None,
                    "End": None,
                    "Instructor (from Instructor)": random_name,
                    "Summary": None,
                    "Email (from Instructor)": random_email,
                    "Recurrence": None,
                },
                "discounts": {
                    "Code": None,
                    "Created": None,
                    "Assigned": None,
                    "Assignee": random_email,
                    "Amount": None,
                    "Expires": None,
                    "Use By": None,
                },
            },
            "policy_enforcement": {
                "sections": {
                    "Section": None,
                    "Policy": None,
                    "id": None,
                    "Violations": None,
                },
                "violations": {
                    "Tag Number": None,
                    "Accrued": None,
                    "Daily Fee": None,
                    "Relevant Sections": None,
                    "Evidence": None,
                    "Fees": None,
                    "Instance #": None,
                    "Closure": None,
                    "Reporter": random_name,
                    "Notes": (lambda _: "A violation occurred"),
                    "Onset": None,
                    "Close date (from Closure)": None,
                    "Closer (from Closure)": random_name,
                    "Section (from Relevant Sections)": None,
                    "Calculation": None,
                    "Notes (from Closure)": (lambda _: "Violation resolved"),
                    "Neon ID": random_id,
                },
                "fees": {
                    "Paid": None,
                    "Violation": None,
                    "Created": None,
                    "ID": None,
                    "Amount": None,
                },
            },
            "people": {
                "shop_tech_forecast_overrides": {
                    "Shift Start": None,
                    "Override": random_name,
                    "Last Modified By": random_name,
                    "Last Modified": None,
                },
                "sign_in_announcements": {
                    "Title": None,
                    "Roles": None,
                    "Message": None,
                    "Published": None,
                    "Tool Codes": None,
                    "Tool Name (from Tool Codes)": None,
                    "Survey": None,
                },
                "sign_in_survey_responses": {},
                "sign_ins": {
                    "Email": random_email,
                    "Waiver Ack": None,
                    "Purpose": None,
                    "Am Member": None,
                    "Created": None,
                    "Full Name": random_name,
                    "Clearances": (lambda _: "ABC: Clearance 1, DEF: Clearance 2"),
                    "Status": None,
                    "Dependent Info": (lambda _: None),
                    "Referrer": None,
                    "Violations": None,
                },
                "automation_intents": {},
            },
        }
        for k, v in get_config("airtable").items():
            for k2 in v.keys():
                if k2 in ("base_id", "token"):
                    continue
                log.info(f"- {k} {k2}...")
                for rec in airtable.get_all_records(k, k2):
                    for field, val in rec["fields"].items():
                        try:
                            fn = table_sanitization[k][k2][field]
                        except KeyError as exc:
                            raise KeyError(
                                f"Failed to lookup sanitizer for {k}/{k2}/{field}"
                            ) from exc
                        if callable(fn):
                            rec["fields"][field] = fn(val)
                    tables[k][k2].append(rec)
        return tables

    def _fetch_neon_accounts(self):
        log.info("Fetching sanitized accounts/memberships from neon...")
        accounts = {}
        memberships = {}
        for acct_id in [
            1797,  # Test Member
            1727,  # Testing Nonmember
            2147,  # Test2 Member
            2148,  # Test3 Member
            2405,  # Testing Alert System
        ]:
            acc, is_company = neon_base.fetch_account(acct_id)
            if acc is None:
                log.warning(f"Unable to fetch account with id {acct_id}, skipping")
            else:
                log.info(f"- Account #{acct_id}")
                acc = self._sanitize_account(acc)
                accounts[acct_id] = (
                    {"companyAccount": acc}
                    if is_company
                    else {"individualAccount": acc}
                )
                memberships[acct_id] = list(neon.fetch_memberships(acct_id))
        return accounts, memberships

    @command(
        arg("--path", help="Path to destination file", type=str, required=True),
        arg("--after", help="Earliest date for event data", type=str, required=True),
    )
    def gen_mock_data(self, args, _):  # pylint: disable=too-many-locals
        """Fetch mock data from airtable, neon etc.
        Write this to a file for running without touching production data"""
        accounts, memberships = self._fetch_neon_accounts()

        tables = self._fetch_airtable()

        log.info("Fetching tool clearance codes from neon...")
        clearance_codes = list(neon.fetch_clearance_codes())

        events, attendees = self._fetch_neon_events(args.after)
        with open(args.path, "wb") as f:
            pickle.dump(
                {
                    "neon": {
                        "events": events,
                        "attendees": attendees,
                        "accounts": accounts,
                        "memberships": memberships,
                        "clearance_codes": clearance_codes,
                    },
                    "airtable": tables,
                },
                f,
            )
        log.info("Done")
