""" Neon CRM integration methods """  # pylint: disable=too-many-lines
import datetime
import logging
from functools import lru_cache

from dateutil import parser as dateparser
from flask import Response

from protohaven_api.config import tz, tznow, utcnow
from protohaven_api.integrations import neon_base
from protohaven_api.integrations.data.neon import CustomField
from protohaven_api.rbac import Role

log = logging.getLogger("integrations.neon")


def fetch_upcoming_events(back_days=7, published=True):
    """Load upcoming events from Neon CRM, with `back_days` of trailing event data.
    Note that querying is done based on the end date so multi-week intensives
    can still appear even if they started earlier than `back_days`."""
    q_params = {
        "endDateAfter": (tznow() - datetime.timedelta(days=back_days)).strftime(
            "%Y-%m-%d"
        ),
        "archived": False,
    }
    if published:
        q_params["publishedEvent"] = published
    return neon_base.paginated_fetch("api_key1", "/events", q_params)


def fetch_events(after=None, before=None, published=True):
    """Load events from Neon CRM"""
    q_params = {
        "publishedEvent": published,
        **({"startDateAfter": after.strftime("%Y-%m-%d")} if after is not None else {}),
        **(
            {"startDateBefore": before.strftime("%Y-%m-%d")}
            if before is not None
            else {}
        ),
    }
    return neon_base.paginated_fetch("api_key1", "/events", q_params)


def search_upcoming_events(from_date, to_date, extra_fields):
    """Lookup upcoming events"""
    return neon_base.paginated_search(
        [
            ("Event Start Date", "GREATER_AND_EQUAL", from_date.strftime("%Y-%m-%d")),
            ("Event Start Date", "LESS_AND_EQUAL", to_date.strftime("%Y-%m-%d")),
        ],
        [
            "Event ID",
            "Event Name",
            "Event Web Publish",
            "Event Web Register",
            *extra_fields,
        ],
        typ="events",
        pagination={"sortColumn": "Event Start Date", "sortDirection": "ASC"},
    )


def fetch_event(event_id):
    """Fetch data on an individual (legacy) event in Neon"""
    return neon_base.get("api_key1", f"/events/{event_id}")


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
    for c in neon_base.get("api_key1", f"/customFields/{CustomField.CLEARANCES}")['optionValues']:
        code, name = c['name'].split(':')
        yield {**c, 'code': code.strip().upper(), 'name': name.strip()}


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


def get_latest_membership_id(account_id):
    """Returns the ID of the membership with the latest start date, or None
    if there are no memberships for the account under `account_id`."""
    latest = (None, None)
    for mem in fetch_memberships(account_id):
        tsd = dateparser.parse(mem["termStartDate"]).astimezone(tz)
        if not latest[1] or latest[1] < tsd:
            latest = (mem["id"], tsd)
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
    assert isinstance(content, list)
    return content


def search_member_by_name(firstname, lastname):
    """Lookup a user by first and last name"""
    for result in neon_base.paginated_search(
        [
            ("First Name", "EQUAL", firstname.strip()),
            ("Last Name", "EQUAL", lastname.strip()),
        ],
        ["Account ID", "Email 1"],
        pagination={"pageSize": 1},
    ):
        return result


def get_inactive_members(extra_fields):
    """Lookup all accounts with inactive memberships"""
    return neon_base.paginated_search(
        [
            ("Account Current Membership Status", "NOT_EQUAL", "Active"),
        ],
        ["Account ID", *extra_fields],
        pagination={"pageSize": 100},
    )


def get_active_members(extra_fields):
    """Lookup all accounts with active memberships"""
    return neon_base.paginated_search(
        [
            ("Account Current Membership Status", "EQUAL", "Active"),
        ],
        ["Account ID", *extra_fields],
        pagination={"pageSize": 100},
    )


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


def search_member(email, operator="EQUAL"):
    """Lookup a user by their email; note that emails aren't unique so we may
    return multiple results."""
    return neon_base.paginated_search(
        [("Email", operator, email)], ["Account ID", *MEMBER_SEARCH_OUTPUT_FIELDS]
    )


def get_members_with_role(role, extra_fields):
    """Fetch all members with a specific assigned role (e.g. all shop techs)"""
    return neon_base.paginated_search(
        [(str(CustomField.API_SERVER_ROLE), "CONTAIN", role["id"])],
        ["Account ID", "First Name", "Last Name", *extra_fields],
    )


def get_new_members_needing_setup(max_days_ago, extra_fields=None):
    """Fetch all members in need of automated setup; this includes
    all paying members past the start of the Onboarding V2 plan
    that haven't yet had automation applied to them."""
    enroll_date = (tznow() - datetime.timedelta(days=max_days_ago)).strftime("%Y-%m-%d")
    return neon_base.paginated_search(
        [
            (str(CustomField.ACCOUNT_AUTOMATION_RAN), "BLANK", None),
            ("First Membership Enrollment Date", "GREATER_THAN", enroll_date),
            ("Membership Cost", "GREATER_THAN", 10),
        ],
        ["Account ID", "First Name", "Last Name", *(extra_fields or [])],
    )


def get_all_accounts_with_discord_association(extra_fields):
    """Lookup all accounts with discord users associated"""
    return neon_base.paginated_search(
        [(str(CustomField.DISCORD_USER), "NOT_BLANK", None)],
        ["Account ID", *extra_fields],
    )


def get_members_with_discord_id(discord_id, extra_fields=None):
    """Fetch all members with a specific Discord ID"""
    return neon_base.paginated_search(
        [(str(CustomField.DISCORD_USER), "EQUAL", discord_id)],
        ["Account ID", "First Name", "Last Name", *(extra_fields or [])],
    )


def fetch_techs_list():
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
                "id": t["Account ID"],
                "name": f"{t['First Name']} {t['Last Name']}",
                "email": t["Email 1"],
                "interest": t.get("Interest", ""),
                "expertise": t.get("Expertise", ""),
                "area_lead": t.get("Area Lead", ""),
                "shift": t.get("Shop Tech Shift", ""),
                "first_day": t.get("Shop Tech First Day", ""),
                "last_day": t.get("Shop Tech Last Day", ""),
                "clearances": (
                    t["Clearances"].split("|")
                    if t.get("Clearances") is not None
                    else []
                ),
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
    for e in search_upcoming_events(
        from_date=now,
        to_date=until,
        extra_fields=[
            "Event Registration Attendee Count",
            "Event Capacity",
            "Event Start Date",
            "Event Start Time",
        ],
    ):
        if e.get("Event Web Publish") != "Yes" or e.get("Event Web Register") != "Yes":
            continue
        capacity = int(e.get("Event Capacity"))
        numreg = int(e.get("Event Registration Attendee Count"))
        if capacity <= numreg:
            continue
        if not e.get("Event Start Date") or not e.get("Event Start Time"):
            continue
        d = dateparser.parse(
            e["Event Start Date"] + " " + e["Event Start Time"]
        ).astimezone(tz)
        d = d.strftime("%b %-d, %-I%p")
        sample_classes.append(
            {
                "url": f"https://protohaven.org/e/{e['Event ID']}",
                "name": e["Event Name"],
                "date": d,
                "seats_left": capacity - numreg,
            }
        )
        if len(sample_classes) >= 3:
            break
    return sample_classes


def create_coupon_code(code, amt):
    """Creates a coupon code for a specific absolute amount"""
    return neon_base.NeonOne().create_single_use_abs_event_discount(code, amt)


def soft_search(keyword):
    """Creates a coupon code for a specific absolute amount"""
    return neon_base.NeonOne().soft_search(keyword)


def patch_member_role(email, role, enabled):
    """Enables or disables a specific role for a user with the given `email`"""
    mem = list(search_member(email))
    if len(mem) == 0:
        raise KeyError()
    account_id = mem[0]["Account ID"]
    roles = neon_base.get_custom_field(account_id, CustomField.API_SERVER_ROLE)
    roles = {v["id"]: v["name"] for v in roles}
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
    """Publishes or unpublishes an event in Neon"""
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
        n.assign_price_to_group(
            event_id,
            group_id,
            p["price_name"],
            round(price * p["price_ratio"]),
            round(seats * p["qty_ratio"]),
        )
