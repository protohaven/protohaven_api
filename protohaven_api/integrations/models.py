"""Objects modeling particular entities that are commonly passed between systems"""

import datetime
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Generator, Optional, Tuple
from urllib.parse import urljoin

from dateutil import parser as dateparser
from dateutil import tz as dtz

from protohaven_api.config import safe_parse_datetime, tznow

log = logging.getLogger("integrations.models")

WAIVER_REGEX = r"version (.+?) on (.*)"


@dataclass
class Role:
    """Every Neon user has zero or more roles that can be checked for access."""

    INSTRUCTOR = {"name": "Instructor", "id": "75"}
    PRIVATE_INSTRUCTOR = {"name": "Private Instructor", "id": "246"}
    BOARD_MEMBER = {"name": "Board Member", "id": "244"}
    STAFF = {"name": "Staff", "id": "245"}
    SHOP_TECH = {"name": "Shop Tech", "id": "238"}
    SHOP_TECH_LEAD = {"name": "Shop Tech Lead", "id": "241"}
    EDUCATION_LEAD = {"name": "Education Lead", "id": "247"}
    ONBOARDING_DEPRECATED = {"name": "Onboarding", "id": "240"}  # DO NOT USE
    ADMIN = {"name": "Admin", "id": "239"}
    SOFTWARE_DEV = {"id": "258", "name": "Software Dev"}
    IT_MAINTENANCE = {"id": "274", "name": "IT Maintenance"}
    MAINTENANCE_CREW = {"id": "259", "name": "Maintenance Crew"}
    MEMBERSHIP_AND_PROGRAMMING = {
        "id": "260",
        "name": "Membership and Programming Committee",
    }
    STRATEGIC_PLANNING = {"id": "261", "name": "Strategic Planning Committee"}
    FINANCE = {"id": "262", "name": "Finance Committee"}
    EXECUTIVE = {"id": "263", "name": "Executive Committee"}
    OPERATIONS = {"id": "266", "name": "Operations Committee"}

    AUTOMATION = {"name": "Automation", "id": None}

    @classmethod
    def as_dict(cls) -> Dict[str, Dict[str, Optional[str]]]:
        """Return dictionary mapping name to the value of each field"""
        results = {}
        for f in dir(cls()):
            v = getattr(cls, f)
            if isinstance(v, dict) and v.get("id") is not None:
                results[v["name"]] = v
        return results


@dataclass
class Membership:
    """An object that facilitates proper and safe typed lookups of membership data from Neon"""

    neon_raw_data: dict = field(default_factory=dict)

    @classmethod
    def from_neon_fetch(cls, data):
        """Parses out all relevant info for a membership
        from the results of a Neon /account GET request"""
        if not data:
            return None
        m = cls()
        m.neon_raw_data = data
        return m

    def is_lapsed(self, now=None) -> bool:
        """Return true if the membership window is in the past, false otherwise"""
        now = (now or tznow()).replace(hour=0, minute=0, second=0, microsecond=0)
        return bool(self.end_date and self.end_date < now)

    @property
    def start_date(self) -> datetime.datetime:
        """Returns the start date of the membership, if any"""
        return (
            safe_parse_datetime(self.neon_raw_data.get("termStartDate"))
            if self.neon_raw_data.get("termStartDate")
            else None
        )

    @property
    def end_date(self) -> datetime.datetime:
        """Return end date, or the maximum possible date if not set"""
        return (
            safe_parse_datetime(self.neon_raw_data.get("termEndDate"))
            if self.neon_raw_data.get("termEndDate")
            else datetime.datetime.max
        )

    @property
    def neon_id(self):
        """Returns neon ID of the membership"""
        return self.neon_raw_data["id"]

    @property
    def level(self) -> str:
        """Returns membership level"""
        return (self.neon_raw_data["membershipLevel"]["name"] or "").strip()

    @property
    def term(self) -> str:
        """Returns membership term"""
        return (self.neon_raw_data["membershipTerm"]["name"] or "").strip()

    def __getattr__(self, attr):
        """Possible attributes: fee, status, autoRenewal"""
        return self.neon_raw_data.get(attr)


@dataclass
class Member:  # pylint:disable=too-many-public-methods
    """A canonical format for all of a Protohaven member's data"""

    neon_raw_data: dict = field(default_factory=dict)
    neon_search_data: dict = field(default_factory=dict)
    neon_membership_data: list[dict] | None = None
    airtable_bio_data: dict = field(default_factory=dict)

    @classmethod
    def from_neon_fetch(cls, data):
        """Parses out all relevant info for a member
        from the results of a Neon /account GET request"""
        if not data:
            return None
        m = cls()
        m.neon_raw_data = data
        return m

    @classmethod
    def from_neon_search(cls, data):
        """Parses out all relevant info for a member from
        the results of a neon /account/search request"""
        if not data:
            return None
        m = cls()
        m.neon_search_data = data
        return m

    def set_membership_data(self, data):
        """Merges in membership information fetched from Neon"""
        self.neon_membership_data = data

    def set_bio_data(self, data):
        """Merges in Airtable profile pic and bio information"""
        self.airtable_bio_data = data

    @property
    def is_paying_member(self) -> bool:
        """Return true if member has an active, nonzero-cost membership"""
        for ms in self.memberships(active_only=True):
            if ms.fee > 0:
                return True

        return False

    def last_membership_expiration_date(
        self,
    ) -> Tuple[datetime.datetime | None, bool | None]:
        """Returns a tuple of (expiration_date, autorenewal) based on
        membership data. Unspecified end date will be treated as "infinite".
        A value of (None, None) will be returned if the account has no memberships
        """
        result: Tuple[datetime.datetime | None, bool | None] = (None, None)
        for m in self.memberships():
            if not result[0] or (m.end_date and result[0] < m.end_date):
                result = (m.end_date, m.autoRenewal or False)
        return result

    def latest_membership(self, active_only=False) -> Membership | None:
        """Gets the membership with start date furthest in the future"""
        latest = None
        for m in self.memberships(active_only):
            if not latest or m.start_date > latest.start_date:
                latest = m
        return latest

    def memberships(self, active_only=False):
        """Fetches Membership instances for all memberships loaded"""
        if self.neon_membership_data is None:
            raise RuntimeError(
                f"No membership data loaded for member instance {self.neon_id}"
            )
        for m in self.neon_membership_data:
            ms = Membership(m)
            if active_only and ms.is_lapsed():
                continue
            yield ms

    def can_reserve_tools(self):
        """True if the member is allowed to reserve tools, false otherwise"""
        return not self.is_company() and self.account_current_membership_status in (
            "Active",
            "Future",
        )

    def is_company(self):
        """True if this is a Neon company account and not an individual account"""
        return self.neon_raw_data.get("companyAccount") or (
            self.company_id and self.company_id == self.neon_id
        )

    def _raw_account(self):
        return (
            self.neon_raw_data.get("individualAccount")
            or self.neon_raw_data.get("companyAccount")
            or {}
        )

    @property
    def fname(self):
        """Get the preferred first name of the member
        Please try to use self.name instead unless interacting
        with a third party service that stores first and last names.
        """
        v = (
            self.neon_search_data.get("Preferred Name")
            or self.neon_search_data.get("First Name")
            or self._raw_account().get("primaryContact", {}).get("firstName")
        )
        return v.strip() if v else None

    @property
    def lname(self):
        """Get the preferred last name of the member
        Please try to use self.name instead unless interacting
        with a third party service that stores first and last names.
        """
        v = self.neon_search_data.get("Last Name") or self._raw_account().get(
            "primaryContact", {}
        ).get("lastName")
        return v.strip() if v else None

    def _resolve_full_name(self, first, preferred, last, pronouns):
        """Convert neon values into a single string of Discord nickname for user"""
        first = first.strip() if first else ""
        preferred = preferred.strip() if preferred else ""
        last = last.strip() if last else ""
        pronouns = pronouns.strip() if pronouns else ""
        first = preferred if preferred != "" else first
        nick = f"{first} {last}".strip() if first != last else first
        if pronouns != "":
            nick += f" ({pronouns})"
        return nick

    @property
    def name(self):
        """Get the fully resolved name and pronouns of the member"""
        return self._resolve_full_name(
            self.neon_search_data.get("First Name")
            or self._raw_account().get("primaryContact", {}).get("firstName"),
            self.neon_search_data.get("Preferred Name"),
            self.neon_search_data.get("Last Name")
            or self._raw_account().get("primaryContact", {}).get("lastName"),
            self.neon_search_data.get("Pronouns")
            or self._get_custom_field("Pronouns", "value"),
        )

    @property
    def email(self):
        """Fetches the first valid email address for the member"""
        v = (
            self.neon_search_data.get("Email 1")
            or self.neon_search_data.get("Email 2")
            or self.neon_search_data.get("Email 3")
            or self._raw_account().get("primaryContact", {}).get("email1")
            or self._raw_account().get("primaryContact", {}).get("email2")
            or self._raw_account().get("primaryContact", {}).get("email3")
        )
        return v.strip().lower() if v else None

    def _get_custom_field(self, key_field, value_field):
        search_result = self.neon_search_data.get(key_field)
        if search_result is not None:
            return search_result
        for cf in self._raw_account().get("accountCustomFields", []):
            if cf["name"] == key_field:
                return cf.get(value_field)
        return None

    def _resolve(self, fetch_field, search_field):
        """Resolve a field from either neon_search_data or neon_raw_data"""
        return (
            self._raw_account().get(fetch_field)
            or self.neon_search_data.get(search_field)
            or None
        )

    @property
    def income_based_rate(self):
        """Return Income Based Rate custom neon field"""
        val = self._get_custom_field("Income Based Rate", "optionValues")
        log.info(f"{val}")
        if isinstance(val, list):
            val = val[0]
        if isinstance(val, dict):
            return val["name"]
        if isinstance(val, str):  # Such as from search results
            return val.strip()
        return None

    @property
    def membership_level(self):
        """Fetches membership level - note that this is only available via search result"""
        if "Membership Level" in self.neon_search_data:
            mem = self.neon_search_data.get("Membership Level")
            return mem
        mem = self.latest_membership(active_only=True)
        if mem:
            return mem.level
        return ""

    @property
    def household_id(self):
        """Fetches household ID - note that this is only available via search result"""
        return self.neon_search_data.get("Household ID") or ""

    @property
    def membership_term(self):
        """Fetches membership term - note that this is only available via search result"""
        mem = self.neon_search_data.get("Membership Term")
        if mem:
            return mem
        mem = self.latest_membership(active_only=True)
        if mem:
            return mem.term
        return ""

    @property
    def proof_of_income(self):
        """Return Proof of Income custom neon field"""
        return self._get_custom_field("Proof of Income", "value")

    @property
    def announcements_acknowledged(self) -> str:
        """Return announcements acknowledged custom neon field"""
        return self._get_custom_field("Announcements Acknowledged", "value") or ""

    @property
    def waiver_accepted(self) -> Tuple[str | None, datetime.datetime | None]:
        """Return version and date of waiver acceptance via custom neon field"""
        v = self._get_custom_field("Waiver Accepted", "value") or ""
        match = re.match(WAIVER_REGEX, v)
        if match is not None:
            last_version = match[1]
            last_signed = safe_parse_datetime(match[2])
            return (last_version, last_signed)
        return (None, None)

    @property
    def notify_board_and_staff(self) -> str:
        """Return Notify Board & Staff custom neon field"""
        return self._get_custom_field("Notify Board & Staff", "value") or ""

    @property
    def company(self):
        """Fetches company information for neon individual account"""
        return self._raw_account().get("company", None)

    @property
    def clearances(self):
        """Fetches clearances for the account"""
        if self.neon_search_data and self.neon_search_data.get("Clearances"):
            return [v.strip() for v in self.neon_search_data["Clearances"].split("|")]
        return [
            v["name"]
            for v in (self._get_custom_field("Clearances", "optionValues") or [])
        ]

    @property
    def roles(self):
        """Fetches all roles associated with the neon account"""
        rdict = Role.as_dict()

        search_result = self.neon_search_data.get("API server role")
        if search_result:
            return [rdict.get(r) for r in search_result.split("|") if r in rdict]

        val = self._get_custom_field("API server role", "optionValues")
        if val:
            return [rdict.get(v["name"]) for v in val if v["name"] in rdict]

        return None

    @property
    def volunteer_bio(self):
        """With bio data, get member bio string"""
        if not self.airtable_bio_data:
            return None
        return self.airtable_bio_data["fields"].get("Bio") or ""

    @property
    def volunteer_picture(self):
        """With bio data, get member's profile picture"""
        if not self.airtable_bio_data:
            return None
        thumbs = self.airtable_bio_data["fields"].get("Picture")[0]["thumbnails"][
            "large"
        ]
        return thumbs.get("url") or urljoin(
            "http://localhost:8080",
            thumbs.get("signedPath"),
        )

    def __getattr__(self, attr):
        """Resolves simple calls to _get_custom_field and _resolve for account data.
        Only called when self.attr doesn't exist - instance attribute access only.
        """
        custom_fields = {
            "discord_user": ("Discord User", "value"),
            "interest": ("Interest", "value"),
            "expertise": ("Expertise", "value"),
            "account_automation_ran": ("Account Automation Ran", "value"),
        }
        if attr in custom_fields:
            return self._get_custom_field(*custom_fields[attr])

        resolvable_fields = {
            "neon_id": ("accountId", "Account ID"),
            "company_id": ("companyId", "Company ID"),
            "account_current_membership_status": (
                "accountCurrentMembershipStatus",
                "Account Current Membership Status",
            ),
        }
        if attr in resolvable_fields:
            return self._resolve(*resolvable_fields[attr])

        day_custom_fields = {
            "zero_cost_ok_until": "Zero-Cost Membership OK Until Date",
            "shop_tech_first_day": "Shop Tech First Day",
            "shop_tech_last_day": "Shop Tech Last Day",
        }
        if attr in day_custom_fields:
            val = self._get_custom_field(day_custom_fields[attr], "value")
            if val is None:
                return None
            try:
                return safe_parse_datetime(val).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            except dateparser.ParserError as e:
                log.error(e)
                return None

        raise AttributeError(attr)

    @property
    def area_lead(self):
        """Return a list of areas this account is an area lead for"""
        v = self._get_custom_field("Area Lead", "value")
        return [] if not v else [a.strip() for a in v.split(",")]

    @property
    def shop_tech_shift(self):
        """Returns the tuple of ("weekday", AM|PM) indicating the
        member's shop tech shift"""
        v = self._get_custom_field("Shop Tech Shift", "value")
        if not isinstance(v, str) or " " not in v:
            return (None, None)
        v = [s.strip() for s in v.split(" ") if s.strip() != ""]
        if len(v) != 2:
            return (None, None)
        return v[0].title(), v[1].upper()

    @property
    def booked_id(self):
        """Return Booked user ID custom field from Neon"""
        got = self._get_custom_field("Booked User ID", "value")
        return int(got) if got else None


@dataclass
class Attendee:
    """A canonical format for event data"""

    neon_raw_data: dict = field(default_factory=dict)
    eventbrite_data: dict = field(default_factory=dict)

    @property
    def neon_id(self):
        """ID of the attendee account"""
        return (
            self.neon_raw_data.get("accountId")
            or self.neon_raw_data.get("registrantAccountId")
            or self.eventbrite_data.get("id")
        )

    @property
    def email(self):
        """Email address of the attendee"""
        return self.neon_raw_data.get("email") or self.eventbrite_data.get(
            "profile", {}
        ).get("email")

    @property
    def fname(self):
        """First name of the attendee"""
        return self.neon_raw_data.get("firstName") or self.eventbrite_data.get(
            "profile", {}
        ).get("first_name")

    @property
    def name(self):
        """Full name of the attendee"""
        return (
            self.fname
            + " "
            + (
                self.neon_raw_data.get("lastName")
                or self.eventbrite_data.get("profile", {}).get("last_name")
            )
        )

    @property
    def valid(self):
        """Return true if the attendee has paid successfully and not cancelled"""
        return self.neon_raw_data.get("registrationStatus") == "SUCCEEDED" or (
            not self.eventbrite_data.get("cancelled")
            and not self.eventbrite_data.get("refunded")
        )


@dataclass
class Event:  # pylint: disable=too-many-public-methods
    """A canonical format for Neon event data"""

    neon_raw_data: dict = field(default_factory=dict)
    neon_search_data: dict = field(default_factory=dict)
    neon_attendee_data: dict | None = field(default=None)
    neon_ticket_data: dict | None = field(default=None)
    eventbrite_data: dict = field(default_factory=dict)
    eventbrite_attendee_data: list | None = field(default=None)
    airtable_data: dict = field(default_factory=dict)

    @classmethod
    def from_neon_fetch(cls, data):
        """Parses out all relevant info from the results of a Neon GET request"""
        if not data:
            return None
        m = cls()
        m.neon_raw_data = data
        return m

    @classmethod
    def from_neon_search(cls, data):
        """Parses out all relevant info from
        the results of a neon /account/search request"""
        if not data:
            return None
        m = cls()
        m.neon_search_data = data
        return m

    @classmethod
    def from_eventbrite_search(cls, data):
        """Parses out all relevant info from eventbrite"""
        if not data:
            return None
        m = cls()
        m.eventbrite_data = data
        return m

    def set_attendee_data(self, data):
        """Adds attendee data to an existing Event instance"""
        if data:
            # We cast to list here as these may be a generator-
            # otherwise it may misreport the number of attendees
            # when called multiple times
            if self.eventbrite_data:
                self.eventbrite_attendee_data = list(data)
            else:
                self.neon_attendee_data = list(data)

    def set_airtable_data(self, data):
        """Adds airtable data to an existing Event instance"""
        if (
            data is not None
            and "Email" in data["fields"]
            and "Instructor" in data["fields"]
            and "Supply Cost (from Class)" in data["fields"]
        ):
            self.airtable_data = data

    def set_ticket_data(self, data):
        """Adds ticketing data to an existing Event instance"""
        self.neon_ticket_data = data

    def _resolve(self, fetch_field, search_field, eventbrite_field=None):
        """Resolve a field from either neon_search_data or neon_raw_data"""
        if self.eventbrite_data and eventbrite_field:
            v = self.eventbrite_data
            for f in eventbrite_field:
                v = v.get(f, {})
            return v if v else None
        return (
            self.neon_raw_data.get(fetch_field)
            or self.neon_search_data.get(search_field)
            or None
        )

    def _resolve_date(self, dtfetch, dtsearch, eb):
        """Returns the start date of the event"""
        if self.eventbrite_data:
            return safe_parse_datetime(self.eventbrite_data.get(eb).get("utc"))

        if self.neon_raw_data:
            # /v2/events/<event_id> returns structured data, while
            # /v2/events returns a flattened data subset
            dates = self.neon_raw_data.get("eventDates") or self.neon_raw_data
            vd = dates.get(dtfetch[0])
            vt = dates.get(dtfetch[1])
        else:
            # /v2/events/search returns humanized string fields
            vd = self.neon_search_data.get(dtsearch[0])
            vt = self.neon_search_data.get(dtsearch[1])

        if vd and vt:
            try:
                return safe_parse_datetime(f"{vd} {vt}")
            except dateparser.ParserError as e:
                log.error(e)
        return None

    @property
    def capacity(self) -> int:
        """Return capcaity of the event"""
        cap = (
            self.neon_raw_data.get("capacity")
            or self.neon_raw_data.get("maximumAttendees")
            or self.neon_search_data.get("Event Capacity")
            or self.eventbrite_data.get("capacity")
        )
        return None if not cap else int(cap)

    @property
    def published(self) -> bool:
        """Return True if published"""
        return (
            self.neon_raw_data.get("publishEvent")
            or (self.neon_search_data.get("Event Web Publish") == "Yes")
            or self.eventbrite_data.get("listed")
            or False
        )

    @property
    def archived(self) -> bool:
        """Return True if archived"""
        return (
            self.neon_raw_data.get("archived")
            or (self.neon_search_data.get("Event Archive") == "Yes")
            or False
        )

    @property
    def registration(self) -> bool:
        """Return True if registration enabled"""
        return (
            self.neon_raw_data.get("enableEventRegistrationForm")
            or (self.neon_search_data.get("Event Web Register") == "Yes")
            or (self.eventbrite_data.get("status") == "live")
            or False
        )

    @property
    def start_date(self):
        """Get the start date of the event

        NOTE: Prefer `start_utc` to reduce DST bugs
        """
        return self._resolve_date(
            ("startDate", "startTime"),
            ("Event Start Date", "Event Start Time"),
            "start",
        )

    @property
    def end_date(self):
        """Get the end date of the event

        NOTE: Prefer `end_utc` to reduce DST bugs
        """
        return self._resolve_date(
            ("endDate", "endTime"), ("Event End Date", "Event End Time"), "end"
        )

    @property
    def start_utc(self):
        """Get the start date of the event in UTC"""
        return self.start_date.astimezone(dtz.UTC) if self.start_date else None

    @property
    def end_utc(self):
        """Get the end date of the event in UTC"""
        return self.end_date.astimezone(dtz.UTC) if self.end_date else None

    @property
    def attendees(self) -> Generator[Attendee, None, None]:
        """With attendee data, returns Attendee instances"""
        for a in self.eventbrite_attendee_data or []:
            at = Attendee()
            at.eventbrite_data = a
            yield at
        for a in self.neon_attendee_data or []:
            at = Attendee()
            at.neon_raw_data = a
            yield at

    @property
    def signups(self) -> set[int]:
        """With attendee data, compute number of unique registrants for the event"""
        if self.neon_attendee_data is None and self.eventbrite_attendee_data is None:
            raise RuntimeError("Missing attendee data for call to signups()")

        return {at.neon_id for at in self.attendees if at.valid}

    @property
    def attendee_count(self) -> int:
        """Return the number of attendees for the event"""
        if self.eventbrite_data:
            n = 0
            for tc in self.eventbrite_data["ticket_classes"]:
                n += tc["quantity_sold"]
            return n
        ac = self.neon_search_data.get("Event Registration Attendee Count")
        return int(ac) if ac is not None else len(self.signups)

    @property
    def occupancy(self):
        """With attendee data, compute occupancy of the event"""
        if not self.neon_attendee_data and not self.eventbrite_data:
            raise RuntimeError("Missing attendee data for call to occupancy()")
        return 0 if not self.capacity else len(self.signups) / self.capacity

    def in_blocklist(self):
        """Return True if this event is in a blocklist of not-useful events"""
        return self.neon_id in (
            3775,  # Equipment clearance
            17631,  # Private instruction
        )

    def has_open_seats_below_price(self, max_price):
        """Returns a count if the event has open seats within max_price"""
        if self.neon_ticket_data is None and not self.eventbrite_data:
            raise RuntimeError(
                "Missing ticket data for call to has_open_seats_below_price"
            )
        for t in self.ticket_options:
            if (
                # Neon offers discounted rates for special groups; eventbrite has no restriction
                (
                    t["name"] == "Single Registration"
                    if self.neon_ticket_data is not None
                    else True
                )
                and t["price"] > 0
                and t["price"] <= max_price
                and t["sold"] < t["total"]
            ):
                return t["total"] - t["sold"]
        return 0

    @property
    def single_registration_ticket_id(self):
        """Get the ticket ID for a "single registration" style event ticket"""
        if self.neon_ticket_data is None and not self.eventbrite_data:
            raise RuntimeError(
                "Missing ticket data for call to single_registration_ticket_id"
            )

        for t in self.ticket_options:
            if t["name"] in ("Single Registration", "General"):
                return t["id"]
        return None

    @property
    def ticket_options(self):
        """Fetch the ticketing options for the event - requires ticket data loaded"""
        for tc in self.eventbrite_data.get("ticket_classes") or []:
            yield {
                "id": tc["id"],
                "name": tc["name"],
                "price": float(tc["cost"]["major_value"]),
                "total": tc["quantity_total"],
                "sold": tc["quantity_sold"],
            }
        for t in self.neon_ticket_data or []:
            yield {
                "id": t["id"],
                "name": t["name"],
                "price": t["fee"],
                "total": t["maxNumberAvailable"],
                "sold": t["maxNumberAvailable"] - t["numberRemaining"],
            }

    @property
    def url(self):
        """Fetches the canonical URL for this event"""
        if self.eventbrite_data:
            return self.eventbrite_data.get("url")
        nid = self.neon_id
        if nid:
            return f"https://protohaven.app.neoncrm.com/np/clients/protohaven/event.jsp?event={nid}"
        return None

    def __getattr__(self, attr):
        """Resolves simple calls to _get_custom_field and _resolve for account data.
        Only called when self.attr doesn't exist - instance attribute access only.
        """
        resolvable_fields = {
            # We should eventually rename neon_id to event_id
            # since we support Eventbrite as well
            "neon_id": ("id", "Event ID", ["id"]),
            "name": ("name", "Event Name", ["name", "text"]),
            "description": (
                "description",
                "Event Description",
                ["description", "html"],
            ),
        }
        if attr in resolvable_fields:
            return self._resolve(*resolvable_fields[attr])

        airtable_fields = {
            "instructor_email": "Email",
            "instructor_name": "Instructor",
            "supply_cost": "Supply Cost (from Class)",
            "volunteer": "Volunteer",
            "supply_state": "Supply State",
        }
        if attr in airtable_fields:
            if not self.airtable_data:
                return None
            v = self.airtable_data["fields"].get(airtable_fields[attr])
            if isinstance(v, list) and len(v) == 1:
                v = v[0]
            if isinstance(v, str):
                v = v.strip()
            return v

        raise AttributeError(attr)


@dataclass
class SignInEvent:
    """A sign-in event from the front desk."""

    airtable_data: dict = field(default_factory=dict)

    @classmethod
    def from_airtable(cls, data):
        """Creates a SignInEvent from a row in the people/sign_ins airtable"""
        if not data:
            return None
        m = cls()
        m.airtable_data = data
        return m

    @property
    def created(self):
        """Returns the date the sign in was recorded, in UTC"""
        c = self.airtable_data["fields"].get("Created")
        if not c:
            return None
        return safe_parse_datetime(c).astimezone(dtz.UTC)

    @property
    def clearances(self):
        """Returns list of clearances"""
        cc = self.airtable_data["fields"].get("Clearances")
        return [c.strip() for c in cc.split(",")] if cc else []

    @property
    def violations(self):
        """Returns listed violations"""
        vv = self.airtable_data["fields"].get("Violations")
        return [v.strip() for v in vv.split(",")] if vv else []

    @property
    def email(self):
        """Returns email, canonicalized"""
        v = self.airtable_data["fields"].get("Email")
        if not v:
            return "UNKNOWN"
        return v.strip().lower()

    def __getattr__(self, attr):
        """Resolves simple calls to _get_custom_field and _resolve for account data.
        Only called when self.attr doesn't exist - instance attribute access only.
        """
        resolvable_fields = {
            "member": ("Am Member", False),
            "email": ("Email", "UNKNOWN"),
            "status": ("Status", "UNKNOWN"),
            "name": ("Full Name", ""),
        }
        if attr in resolvable_fields:
            k, d = resolvable_fields[attr]
            return self.airtable_data["fields"].get(k) or d
        raise AttributeError(attr)
