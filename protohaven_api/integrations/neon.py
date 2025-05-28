""" Neon CRM integration methods """  # pylint: disable=too-many-lines

import datetime
import logging
from functools import lru_cache

import rapidfuzz
from dateutil import parser as dateparser
from flask import Response

from protohaven_api.config import tz, tznow, utcnow
from protohaven_api.integrations import neon_base
from protohaven_api.integrations.data.neon import CustomField
from protohaven_api.integrations.data.warm_cache import WarmDict
from protohaven_api.integrations.models import Event, Member, Role

log = logging.getLogger("integrations.neon")


def _search_upcoming_events(from_date, to_date):
    """Lookup upcoming events"""
    for evt in neon_base.paginated_search(
        [
            ("Event Start Date", "GREATER_AND_EQUAL", from_date.strftime("%Y-%m-%d")),
            ("Event Start Date", "LESS_AND_EQUAL", to_date.strftime("%Y-%m-%d")),
        ],
        [
            "Event ID",
            "Event Name",
            "Event Web Publish",
            "Event Web Register",
            "Event Registration Attendee Count",
            "Event Capacity",
            "Event Start Date",
            "Event Start Time",
        ],
        typ="events",
        pagination={"sortColumn": "Event Start Date", "sortDirection": "ASC"},
    ):
        yield Event.from_neon_search(evt)


def fetch_event(event_id):
    """Fetch data on an individual (legacy) event in Neon"""
    return Event.from_neon_fetch(neon_base.get("api_key1", f"/events/{event_id}"))


def fetch_registrations(event_id):
    """Fetch registrations for a specific Neon event"""
    return neon_base.paginated_fetch(
        "api_key1", f"/events/{event_id}/eventRegistrations"
    )


def register_for_event(account_id, event_id, ticket_id):
    """Register for `event_id` with `account_id`"""
    return neon_base.post(
        "api_key3",
        "/eventRegistrations",
        {
            "eventId": event_id,
            "registrationAmount": 0,
            "ignoreCapacity": False,
            "sendSystemEmail": True,
            "registrantAccountId": account_id,
            "totalCharge": 0,
            "registrationDateTime": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tickets": [
                {
                    "ticketId": ticket_id,
                    "attendees": [{"accountId": account_id}],
                }
            ],
        },
    )


def delete_single_ticket_registration(account_id, event_id):
    """Deletes single-ticket, single-attendee registrations
    for event with `event_id` made by `account_id`. This
    works for registrations created with `register_for_event()`."""
    for reg in fetch_registrations(event_id):
        tickets = reg.get("tickets", [])
        if len(tickets) != 1:
            continue
        attendees = tickets[0].get("attendees", {})
        if len(attendees) != 1:
            continue

        if attendees[0]["accountId"] == account_id:
            return neon_base.delete("api_key3", f"/eventRegistrations/{reg['id']}")
    return Response(
        f"Registration not found for account {account_id} in event {event_id}",
        status=404,
    )


def fetch_tickets(event_id):
    """Fetch ticket information for a specific Neon event"""
    content = neon_base.get("api_key1", f"/events/{event_id}/tickets")
    assert isinstance(content, list)
    return content


def fetch_memberships(account_id):
    """Fetch membership history of an account in Neon"""
    return neon_base.paginated_fetch("api_key2", f"/accounts/{account_id}/memberships")


def fetch_attendees(event_id):
    """Fetch attendee data on an individual (legacy) event in Neon"""
    return neon_base.paginated_fetch("api_key1", f"/events/{event_id}/attendees")


@lru_cache(maxsize=1)
def fetch_clearance_codes():
    """Fetch all the possible clearance codes that can be used in Neon"""
    rep = neon_base.get("api_key1", f"/customFields/{CustomField.CLEARANCES}")
    result = []
    for c in rep["optionValues"]:
        code, _ = c["name"].split(":")
        result.append({**c, "code": code.strip().upper()})
    return result


def create_zero_cost_membership(account_id, start, end, level=None, term=None):
    """Creates a $0 membership attached to a neon account"""
    return neon_base.post(
        "api_key2",
        "/memberships",
        {
            "accountId": account_id,
            "membershipLevel": level or {"id": 1, "name": "General Membership"},
            "membershipTerm": term or {"id": 1, "name": "General - $115/mo (Join)"},
            "termStartDate": start.strftime("%Y-%m-%d"),
            "termEndDate": end.strftime("%Y-%m-%d"),
            "termUnit": "MONTH",
            "transactionDate": tznow().strftime("%Y-%m-%d"),
            "autoRenewal": False,
            "enrollType": "JOIN",
            "fee": 0,
            "totalCharge": 0,  # Zero fees are normally not auto-deferred on prod; allows us to test
            "status": "SUCCEEDED",
        },
    )


def get_latest_membership_id_and_name(account_id):
    """Returns the ID and level of the membership with the latest start date, or None
    if there are no memberships for the account under `account_id`."""
    latest = ((None, None), None)
    for mem in fetch_memberships(account_id):
        tsd = dateparser.parse(mem["termStartDate"]).astimezone(tz)
        if not latest[1] or latest[1] < tsd:
            latest = ((mem["id"], mem["membershipLevel"]["name"]), tsd)
    return latest[0]


def set_membership_date_range(membership_id, start, end):
    """Sets the termStartDate of the membership with id `membership_id`."""
    return neon_base.patch(
        "api_key2",
        f"/memberships/{membership_id}",
        {
            "termStartDate": start.strftime("%Y-%m-%d"),
            "termEndDate": end.strftime("%Y-%m-%d"),
        },
    )


def set_interest(account_id, interest: str):
    """Assign interest to user custom field"""
    return neon_base.set_custom_fields(account_id, (CustomField.INTEREST, interest))


def set_discord_user(account_id, discord_user: str):
    """Sets the discord user used by this user"""
    return neon_base.set_custom_fields(
        account_id, (CustomField.DISCORD_USER, discord_user)
    )


def set_booked_user_id(account_id, booked_id: str):
    """Sets the Booked Scheduler ID for this user"""
    return neon_base.set_custom_fields(
        account_id, (CustomField.BOOKED_USER_ID, booked_id)
    )


def set_clearances(account_id, code_ids, is_company=None):
    """Sets all clearances for a specific user - company or individual"""
    return neon_base.set_custom_fields(
        account_id,
        (CustomField.CLEARANCES, [{"id": i} for i in code_ids]),
        is_company=is_company,
    )


def fetch_search_fields():
    """Fetches possible search fields for member search"""
    content = neon_base.get("api_key2", "/accounts/search/searchFields")
    assert isinstance(content, list)
    return content


def fetch_output_fields():
    """Fetches possible output fields for member search"""
    content = neon_base.get("api_key2", "/accounts/search/outputFields")
    assert isinstance(content, dict)
    return content


def get_inactive_members(extra_fields: list[str]) -> list[Member]:
    """Lookup all accounts with inactive memberships"""
    for acct in neon_base.paginated_search(
        [
            ("Account Current Membership Status", "NOT_EQUAL", "Active"),
        ],
        ["Account ID", *extra_fields],
        pagination={"pageSize": 100},
    ):
        yield Member.from_neon_search(acct)


def get_active_members(extra_fields: list[str]) -> list[Member]:
    """Lookup all accounts with active memberships"""
    for acct in neon_base.paginated_search(
        [
            ("Account Current Membership Status", "EQUAL", "Active"),
        ],
        ["Account ID", *extra_fields],
        pagination={"pageSize": 100},
    ):
        yield Member.from_neon_search(acct)


MEMBER_SEARCH_OUTPUT_FIELDS = [
    "Household ID",
    "Company ID",
    "First Name",
    "Last Name",
    "Account Current Membership Status",
    "Membership Level",
    "Membership Term",
    CustomField.CLEARANCES,
    CustomField.DISCORD_USER,
    CustomField.WAIVER_ACCEPTED,
    CustomField.ANNOUNCEMENTS_ACKNOWLEDGED,
    CustomField.API_SERVER_ROLE,
    CustomField.NOTIFY_BOARD_AND_STAFF,
]


def search_member(email, operator="EQUAL", fields=None):
    """Lookup a user by their email; note that emails aren't unique so we may
    return multiple results."""
    if not fields:
        fields = MEMBER_SEARCH_OUTPUT_FIELDS
    for acct in neon_base.paginated_search(
        [("Email", operator, email)], ["Account ID", *fields]
    ):
        yield Member.from_neon_search(acct)


def get_members_with_role(role, extra_fields):
    """Fetch all members with a specific assigned role (e.g. all shop techs)"""
    for acct in neon_base.paginated_search(
        [(str(CustomField.API_SERVER_ROLE), "CONTAIN", role["id"])],
        ["Account ID", "First Name", "Last Name", *extra_fields],
    ):
        yield Member.from_neon_search(acct)


def get_new_members_needing_setup(max_days_ago, extra_fields=None):
    """Fetch all members in need of automated setup; this includes
    all paying members past the start of the Onboarding V2 plan
    that haven't yet had automation applied to them."""
    enroll_date = (tznow() - datetime.timedelta(days=max_days_ago)).strftime("%Y-%m-%d")
    for acct in neon_base.paginated_search(
        [
            (str(CustomField.ACCOUNT_AUTOMATION_RAN), "BLANK", None),
            ("First Membership Enrollment Date", "GREATER_THAN", enroll_date),
            ("Membership Cost", "GREATER_THAN", 10),
        ],
        ["Account ID", "First Name", "Last Name", *(extra_fields or [])],
    ):
        return Member.from_neon_search(acct)


def get_all_accounts_with_discord_association(extra_fields):
    """Lookup all accounts with discord users associated"""
    for acct in neon_base.paginated_search(
        [(str(CustomField.DISCORD_USER), "NOT_BLANK", None)],
        ["Account ID", *extra_fields],
    ):
        return Member.from_neon_search(acct)


def get_members_with_discord_id(discord_id, extra_fields=None):
    """Fetch all members with a specific Discord ID"""
    for acct in neon_base.paginated_search(
        [(str(CustomField.DISCORD_USER), "EQUAL", discord_id)],
        ["Account ID", "First Name", "Last Name", *(extra_fields or [])],
    ):
        return Member.from_neon_search(acct)


def fetch_techs_list(include_pii=False):
    """Fetches a list of current shop techs, ordered by number of clearances"""
    techs = []
    for t in get_members_with_role(
        Role.SHOP_TECH,
        [
            "Email 1",
            CustomField.CLEARANCES,
            CustomField.INTEREST,
            CustomField.EXPERTISE,
            CustomField.AREA_LEAD,
            CustomField.SHOP_TECH_SHIFT,
            CustomField.SHOP_TECH_FIRST_DAY,
            CustomField.SHOP_TECH_LAST_DAY,
        ],
    ):
        techs.append(
            {
                "id": t.neon_id if include_pii else "",
                "name": (f"{t.fname} {t.lname}" if include_pii else f"{t.fname}"),
                "email": t.email if include_pii else "",
                "interest": t.interest or "",
                "expertise": t.expertise or "",
                "area_lead": t.area_lead or "",
                "shift": t.shop_tech_shift or "",
                "first_day": t.shop_tech_first_day or "",
                "last_day": t.shop_tech_last_day or "",
                "clearances": t.clearances,
            }
        )
    techs.sort(key=lambda t: len(t["clearances"]))
    return techs


@lru_cache(maxsize=1)
def get_sample_classes(cache_bust, until=10):  # pylint: disable=unused-argument
    """Fetch sample classes for advertisement on the homepage"""
    sample_classes = []
    now = tznow()
    until = tznow() + datetime.timedelta(days=until)
    for evt in _search_upcoming_events(
        from_date=now,
        to_date=until,
    ):
        if not evt.published or not evt.registration or not evt.start_date:
            continue
        if not evt.attendee_count or evt.capacity <= evt.attendee_count:
            continue
        sample_classes.append(
            {
                "url": f"https://protohaven.org/e/{evt.neon_id}",
                "name": evt.name,
                "date": evt.start_date.strftime("%b %-d, %-I%p"),
                "seats_left": evt.capacity - evt.attendee_count,
            }
        )
        if len(sample_classes) >= 3:
            break
    return sample_classes


def create_coupon_code(code, amt, from_date=None, to_date=None):
    """Creates a coupon code for a specific absolute amount"""
    return neon_base.NeonOne().create_single_use_abs_event_discount(
        code, amt, from_date, to_date
    )


def patch_member_role(email, role, enabled):
    """Enables or disables a specific role for a user with the given `email`"""
    mem = list(search_member(email))
    if len(mem) == 0:
        raise KeyError()
    account_id = mem[0].neon_id
    acct = neon_base.fetch_account(account_id, required=True)
    roles = {v["id"]: v["name"] for v in acct.roles}
    if enabled:
        roles[role["id"]] = role["name"]
    elif role["id"] in roles:
        del roles[role["id"]]
    return neon_base.set_custom_fields(
        account_id,
        (CustomField.API_SERVER_ROLE, [{"id": k, "name": v} for k, v in roles.items()]),
    )


def set_tech_custom_fields(  # pylint: disable=too-many-arguments
    account_id,
    shift=None,
    first_day=None,
    last_day=None,
    area_lead=None,
    interest=None,
    expertise=None,
):
    """Overwrites existing waiver status information on an account"""
    cf = [
        (CustomField.SHOP_TECH_SHIFT, shift),
        (CustomField.SHOP_TECH_FIRST_DAY, first_day),
        (CustomField.SHOP_TECH_LAST_DAY, last_day),
        (CustomField.AREA_LEAD, area_lead),
        (CustomField.INTEREST, interest),
        (CustomField.EXPERTISE, expertise),
    ]
    return neon_base.set_custom_fields(account_id, *[v for v in cf if v[1] is not None])


def set_waiver_status(account_id, new_status):
    """Overwrites existing waiver status information on an account"""
    return neon_base.set_custom_fields(
        account_id, (CustomField.WAIVER_ACCEPTED, new_status)
    )


def update_announcement_status(account_id, now=None):
    """Updates announcement acknowledgement"""
    if now is None:
        now = tznow()
    return neon_base.set_custom_fields(
        account_id, (CustomField.ANNOUNCEMENTS_ACKNOWLEDGED, now.strftime("%Y-%m-%d"))
    )


def update_account_automation_run_status(account_id, status: str, now=None):
    """Updates automation ran timestamp"""
    return neon_base.set_custom_fields(
        account_id,
        (
            CustomField.ACCOUNT_AUTOMATION_RAN,
            status + " " + (now or tznow()).strftime("%Y-%m-%d"),
        ),
    )


def set_event_scheduled_state(neon_id, scheduled=True):
    """Publishes or unpublishes an event in Neon, including registration
    and public visibility in protohaven.org/classes/"""
    return neon_base.patch(
        "api_key3",
        f"/events/{neon_id}",
        {
            "publishEvent": scheduled,
            "enableEventRegistrationForm": scheduled,
            "archived": not scheduled,
            "enableWaitListing": scheduled,
        },
    )["id"]


def assign_pricing(  # pylint: disable=too-many-arguments
    event_id, price, seats, clear_existing=False, include_discounts=True, n=None
):
    """Assigns ticket pricing and quantities for a preexisting Neon event"""
    n = n or neon_base.NeonOne()
    if clear_existing:
        n.delete_all_prices_and_groups(event_id)

    for p in neon_base.pricing if include_discounts else neon_base.pricing[:1]:
        log.debug(f"Assign pricing: {p['name']}")
        group_id = n.upsert_ticket_group(
            event_id, group_name=p["name"], group_desc=p["desc"]
        )
        if p.get("cond", None) is not None:
            n.assign_condition_to_group(event_id, group_id, p["cond"])

        # Some classes have so few seats that the ratio rounds down to zero
        # We just skip those here.
        qty = round(seats * p["qty_ratio"])
        if qty <= 0:
            continue
        n.assign_price_to_group(
            event_id,
            group_id,
            p["price_name"],
            round(price * p["price_ratio"]),
            qty,
        )


# Sign-ins need to be speedy; if it takes more than half a second, folks will
# disengage.
class AccountCache(WarmDict):
    """Prefetches account information for faster lookup.
    Lookups are case-insensitive (to match email spec)"""

    NAME = "neon_accounts"
    REFRESH_PD_SEC = datetime.timedelta(hours=24).total_seconds()
    RETRY_PD_SEC = datetime.timedelta(minutes=5).total_seconds()
    FIELDS = [
        *MEMBER_SEARCH_OUTPUT_FIELDS,
        "Email 1",
        CustomField.ACCOUNT_AUTOMATION_RAN,
        CustomField.BOOKED_USER_ID,
        CustomField.INCOME_BASED_RATE,
    ]

    def __init__(self):
        super().__init__()
        self.by_booked_id = {}  # 1:1 mapping of user IDs in booked to users in Neon
        self.fuzzy = {}

    def _value_has_active_membership(self, v):
        for a in v.values():
            if a.account_current_membership_status == "Active":
                return True
        return False

    def _handle_inactive_or_notfound(self, k, v):
        if not v or not self._value_has_active_membership(v):
            aa = list(search_member(k, fields=self.FIELDS))
            if len(aa) > 0:
                log.info(f"cache miss on '{k}' returned results: {aa}")
                return {a.neon_id: a for a in aa}
        return v

    def get(self, k, default=None):
        """Attempt to lookup from cache, but verify directly with Neon if
        the returned account is inactive or missing"""
        return self._handle_inactive_or_notfound(
            str(k), super().get(str(k).lower().strip(), default)
        )

    def __setitem__(self, k, v):
        return super().__setitem__(str(k).lower(), v)

    def __getitem__(self, k):
        """__getitem__ is patched to call out to Neon in the event of a cache
        miss which would normally raise a KeyError"""
        k = str(k)
        try:
            return self._handle_inactive_or_notfound(
                k, super().__getitem__(str(k).lower())
            )
        except KeyError as err:
            v = self._handle_inactive_or_notfound(k, None)
            if not v:
                raise KeyError("Cache miss failover returned no result") from err
            return v

    def update(self, a: Member):
        """Updates cache based on an account dictionary object"""
        d = super().get(a.email, {})  # Don't trigger cache miss
        d[a.neon_id] = a
        self[a.email] = d
        self.fuzzy[rapidfuzz.utils.default_process(f"{a.fname} {a.lname}")] = a[
            "Email 1"
        ]
        self.fuzzy[rapidfuzz.utils.default_process(f"{a.email}")] = a.email
        if a.booked_id:
            self.by_booked_id[a.booked_id] = a

    def refresh(self):
        """Refresh values; called every REFRESH_PD"""
        self.log.info("Beginning AccountCache refresh")
        n = 0
        for a in get_inactive_members(self.FIELDS):
            self.update(a)
            n += 1
            if n % 100 == 0:
                self.log.info(n)
        for a in get_active_members(self.FIELDS):
            self.update(a)
            n += 1
            if n % 100 == 0:
                self.log.info(n)

        self.log.info(
            f"Fetched {n} total accounts / {len(self.by_booked_id.keys())} total mapped "
            f"booked IDs; next refresh in {self.REFRESH_PD_SEC} seconds"
        )

    def neon_id_from_booked_id(self, booked_id: int) -> str:
        """Fetches the Neon ID associated with a Booked user ID"""
        return self.by_booked_id[booked_id].neon_id

    def _find_best_match_internal(self, search_string, top_n=10):
        """Find and return the top_n best matches to the key in `self` based on a search string."""
        # Could probably use a priority queue / heap here for faster lookups, but we only have
        # ~1000 or so records to sort through anyways.
        # Not worth the optimization.

        for m in rapidfuzz.process.extract(
            rapidfuzz.utils.default_process(search_string),
            self.fuzzy,
            scorer=rapidfuzz.fuzz.WRatio,
            score_cutoff=15,
            limit=top_n,
        ):
            yield m[0]

    def find_best_match(self, search_string, top_n=10):
        """Deduplicates find_best_match_internal"""
        result = set()
        for m in self._find_best_match_internal(search_string, 2 * top_n):
            if m in result:
                continue
            result.add(m)
            # Avoid cache misses on lookup
            yield from super().get(m).values()
            if len(result) >= top_n:
                break


cache = AccountCache()
