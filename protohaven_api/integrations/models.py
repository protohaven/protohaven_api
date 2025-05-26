"""Objects modeling particular entities that are commonly passed between systems"""
import datetime
import logging
import re
from dataclasses import dataclass, field

from dateutil import parser as dateparser

from protohaven_api.config import tz

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
    def as_dict(cls):
        """Return dictionary mapping name to the value of each field"""
        results = {}
        for f in dir(cls()):
            v = getattr(cls, f)
            if isinstance(v, dict) and v.get("id") is not None:
                results[v["name"]] = v
        return results


@dataclass
class Member:  # pylint:disable=too-many-public-methods
    """A canonical format for all of a Protohaven member's data"""

    neon_raw_data: dict = field(default_factory=dict)
    neon_search_data: dict = field(default_factory=dict)
    airtable_data: dict = field(default_factory=dict)

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

    def is_company(self):
        """True if this is a Neon company account and not an individual account"""
        return self.neon_raw_data.get("companyAccount")

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
            or self._raw_account()["primaryContact"]["email1"]
            or self._raw_account()["primaryContact"]["email2"]
            or self._raw_account()["primaryContact"]["email3"]
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
    def zero_cost_ok_until(self):
        """Returns the date until which a zero cost membership is OK for this member"""
        val = self._get_custom_field("Zero-Cost Membership OK Until Date", "value")
        try:
            return dateparser.parse(val).astimezone(tz)
        except dateparser.ParserError as e:
            log.error(e)
            return None

    @property
    def income_based_rate(self):
        """Return Income Based Rate custom neon field"""
        val = self._get_custom_field("Income Based Rate", "optionValues")
        if val:
            return val[0]["name"]
        return None

    @property
    def membership_level(self):
        """Fetches membership level - note that this is only available via search result"""
        return self.neon_search_data.get("Membership Level") or ""

    @property
    def household_id(self):
        """Fetches household ID - note that this is only available via search result"""
        return self.neon_search_data.get("Household ID") or ""

    @property
    def membership_term(self):
        """Fetches membership term - note that this is only available via search result"""
        return self.neon_search_data.get("Membership Term") or ""

    @property
    def proof_of_income(self):
        """Return Proof of Income custom neon field"""
        return self._get_custom_field("Proof of Income", "value")

    @property
    def announcements_acknowledged(self) -> str:
        """Return announcements acknowledged custom neon field"""
        return self._get_custom_field("Announcements Acknowledged", "value") or ""

    @property
    def waiver_accepted(self) -> (str | None, datetime.datetime | None):
        """Return version and date of waiver acceptance via custom neon field"""
        v = self._get_custom_field("Waiver Accepted", "value") or ""
        match = re.match(WAIVER_REGEX, v)
        if match is not None:
            last_version = match[1]
            last_signed = dateparser.parse(match[2]).astimezone(tz)
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
            return [v.strip() for v in self.neon_search_data["Clearances"]]
        return [v["name"] for v in self._get_custom_field("Clearances", "optionValues")]

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

    def __getattr__(self, attr):
        """Resolves simple calls to _get_custom_field and _resolve for account data.
        Only called when self.attr doesn't exist - instance attribute access only.
        """
        custom_fields = {
            "discord_user": ("Discord User", "value"),
            "interest": ("Interest", "value"),
            "area_lead": ("Area Lead", "value"),
            "shop_tech_shift": ("Shop Tech Shift", "value"),
            "shop_tech_first_day": ("Shop Tech First Day", "value"),
            "shop_tech_last_day": ("Shop Tech Last Day", "value"),
            "account_automation_ran": ("Account Automation Ran", "value"),
        }
        resolvable_fields = {
            "neon_id": ("accountId", "Account ID"),
            "company_id": ("companyId", "Company ID"),
            "account_current_membership_status": (
                "accountCurrentMembershipStatus",
                "Account Current Membership Status",
            ),
        }
        if attr in custom_fields:
            return self._get_custom_field(*custom_fields[attr])
        if attr in resolvable_fields:
            return self._resolve(*resolvable_fields[attr])
        raise AttributeError(attr)

    @property
    def booked_id(self):
        """Return Booked user ID custom field from Neon"""
        got = self._get_custom_field("Booked User ID", "value")
        return int(got) if got else None
