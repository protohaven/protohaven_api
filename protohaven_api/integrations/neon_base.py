"""Helper methods for the code in integrations.neon"""

import datetime
import json
import logging
import re
import time
import urllib

import pyotp
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from protohaven_api.config import get_config, tznow
from protohaven_api.integrations.data.connector import get as get_connector
from protohaven_api.integrations.data.neon import Category
from protohaven_api.integrations.models import Member

log = logging.getLogger("integrations.neon_base")

BASE_URL = get_config("neon/base_url")
ADMIN_URL = get_config("neon/admin_url")
SSO_URL = get_config("neon/sso_url")


def paginated_fetch(api_key, path, params=None, batching=False):
    """Issue GET requests against Neon's V2 API, yielding all results across
    all result pages"""
    current_page = 0
    total_pages = 1
    result_field = path.split("/")[-1]
    params = params or {}
    while current_page < total_pages:
        params["currentPage"] = current_page
        content = get_connector().neon_request(
            get_config("neon")[api_key],
            "GET",
            urllib.parse.urljoin(BASE_URL, path.lstrip("/"))
            + f"?{urllib.parse.urlencode(params)}",
        )
        if isinstance(content, list):
            raise RuntimeError(f"Got content of type list, expected dict: {content}")
        total_pages = content["pagination"]["totalPages"]
        if content[result_field]:
            if batching:
                yield content[result_field]
            else:
                yield from content[result_field]
        current_page += 1
        log.info(f"paginated_fetch {current_page} / {total_pages} fetched")


def paginated_search(search_fields, output_fields, typ="accounts", pagination=None):
    """Issue POST requests against Neon's V2 API, yielding all results across
    all result pages"""
    cur = 0
    data = {
        "searchFields": [
            {"field": f, "operator": o, "value": v} for f, o, v in search_fields
        ],
        "outputFields": list(
            set(output_fields)
        ),  # Prevent duplicates; causes neon request failure
        "pagination": {"currentPage": cur, "pageSize": 50, **(pagination or {})},
    }
    total = 1
    while cur < total:
        content = get_connector().neon_request(
            get_config("neon/api_key2"),
            "POST",
            urllib.parse.urljoin(BASE_URL, f"{typ}/search"),
            data=json.dumps(data),
            headers={"content-type": "application/json"},
        )
        if content.get("searchResults") is None or content.get("pagination") is None:
            raise RuntimeError(f"Search failed: {content}")

        total = content["pagination"]["totalPages"]
        cur += 1
        data["pagination"]["currentPage"] = cur
        log.info(f"paginated_search {cur} / {total} fetched")
        yield from content["searchResults"]


def fetch_memberships_internal_do_not_call_directly(account_id):
    """Fetch membership history of an account in Neon"""
    return list(paginated_fetch("api_key2", f"/accounts/{account_id}/memberships"))


def fetch_account(account_id, required=False, raw=False, fetch_memberships=False):
    """Fetches account information for a specific user in Neon, as a Member()
    Raises RuntimeError if an error is returned from the server, or None
    if the account is not found.
    """
    content = get("api_key1", f"/accounts/{account_id}")
    if isinstance(content, list):
        raise RuntimeError(content)
    if content is None and required:
        raise RuntimeError(f"Account not found: {account_id}")
    if content is None and not required:
        return None
    if raw:
        return content
    m = Member.from_neon_fetch(content)

    if callable(fetch_memberships):
        fetch_memberships = fetch_memberships(m)

    if fetch_memberships:
        m.set_membership_data(
            fetch_memberships_internal_do_not_call_directly(account_id)
        )
    return m


def get(api_key, path):
    """Send an HTTP GET request"""
    return get_connector().neon_request(
        get_config("neon")[api_key],
        "GET",
        urllib.parse.urljoin(BASE_URL, path.lstrip("/")),
    )


def _req(api_key, path, method, body):
    log.info(f"{api_key} {path} {method}")
    return get_connector().neon_request(
        get_config("neon")[api_key],
        method,
        urllib.parse.urljoin(BASE_URL, path.lstrip("/")),
        data=json.dumps(body),
        headers={"content-type": "application/json"},
    )


def patch(api_key, path, body):
    """Send an HTTP PATCH request"""
    return _req(api_key, path, "PATCH", body)


def put(api_key, path, body):
    """Send an HTTP PUT request"""
    return _req(api_key, path, "PUT", body)


def post(api_key, path, body):
    """Send an HTTP POST request"""
    return _req(api_key, path, "POST", body)


def delete(api_key, path):
    """Send an HTTP DELETE request"""
    return get_connector().neon_request(
        get_config("neon")[api_key],
        "DELETE",
        urllib.parse.urljoin(BASE_URL, path.lstrip("/")),
    )


def patch_account(account_id, data, is_company=None):
    """Patch an existing account via Neon V2 API"""
    if is_company is None:
        acct = fetch_account(account_id, required=True)
        if acct:
            is_company = acct.is_company()
    return patch(
        "api_key2",
        f"/accounts/{account_id}",
        {"companyAccount": data} if is_company else {"individualAccount": data},
    )


def extract_custom_field(acc, field_id):
    """Extracts a custom field's value from a fetched account"""
    field_id = str(field_id)
    for cf in acc.get("accountCustomFields", []):
        if cf["id"] == field_id:
            return cf.get("value") or cf.get("optionValues")
    return []


def set_custom_fields(account_id, *fields, is_company=None):
    """Set any custom field for a user in Neon"""
    return patch_account(
        account_id,
        {
            "accountCustomFields": [
                (
                    {"id": field_id, "optionValues": value}
                    if isinstance(value, list)
                    else {"id": field_id, "value": value}
                )
                for field_id, value in fields
            ]
        },
        is_company,
    )


class DuplicateRequestToken:  # pylint: disable=too-few-public-methods
    """A quick little emulator of the duplicate request token behavior on Neon's site"""

    def __init__(self):
        self.i = int(time.time())

    def get(self):
        """Gets a new dupe token"""
        self.i += 1
        return self.i


class NeonOne:  # pylint: disable=too-few-public-methods
    """Masquerade as a web user to perform various actions not available in the public API"""

    TYPE_MEMBERSHIP_DISCOUNT = 2
    TYPE_EVENT_DISCOUNT = 3

    def __init__(self):
        self.drt = DuplicateRequestToken()
        self.totp = pyotp.TOTP(get_config("neon/login_otp_code"))

    def do_login(self, page):
        """Performs user login, handling second factor OTP if needed"""
        # Navigate to the login page
        page.goto("https://app.neoncrm.com/np/ssoAuth")

        # Fill in the login form. Adjust the selectors to match your form.
        log.info("Filling email")
        page.fill("input[name='email']", get_config("neon/login_user"))
        page.locator('button:text("Next")').click()

        log.info("Filling password")
        page.fill("input[name='password']", get_config("neon/login_pass"))

        # Submit the form
        log.info("Submitting the form")
        page.click("button[type='submit']")

        # Wait for navigation after login
        log.info("Waiting for navigation")
        page.wait_for_url("**/mfa")  # Change to your expected post-login URL

        log.info("Filling MFA code")
        page.fill("input[name='mfa_code']", self.totp.now())
        log.info("Submitting the MFA code form")
        page.click("button[type='submit']")

        page.wait_for_url("**/contentList.do")  # Change to your expected post-login URL

        log.info("Login successful!")

    def create_single_use_abs_event_discounts(
        self, codes, amt, from_date=None, to_date=None
    ):
        """Creates an absolute discount, usable once"""
        with sync_playwright() as p:
            # Launch a headless Firefox browser
            browser = p.firefox.launch(
                headless=True
            )  # Set headless=False for debugging
            page = browser.new_page()
            try:
                self.do_login(page)
            except PlaywrightTimeoutError:
                log.error(
                    "Timed out on first login attempt - trying again in 10 seconds..."
                )
                time.sleep(10.0)
                self.do_login(page)

            for code in codes:
                yield self._post_discount(
                    page,
                    self.TYPE_EVENT_DISCOUNT,
                    code=code,
                    pct=False,
                    amt=amt,
                    from_date=from_date,
                    to_date=to_date,
                )

            browser.close()

    def _post_discount(  # pylint: disable=too-many-arguments
        self,
        page,
        _,  # Previously discount type
        code,
        pct,
        amt,
        from_date="11/19/2023",
        to_date="11/21/2024",
        max_uses=1,
    ):
        log.info(f"filling discount form for code {code}")
        if from_date is None:
            from_date = tznow()
        if to_date is None:
            to_date = from_date + datetime.timedelta(days=90)
        from_date = from_date.strftime("%m/%d/%Y")
        to_date = to_date.strftime("%m/%d/%Y")

        page.goto(
            "https://protohaven.app.neoncrm.com/np/admin/systemsetting/"
            "newCouponCodeDiscount.do?sellingItemType=3&discountType=1"
        )
        page.fill("input[name='currentDiscount.couponCode']", code)
        page.fill("input[name='currentDiscount.maxUses']", str(max_uses))
        page.fill("input[name='currentDiscount.validFromDate']", from_date)
        page.fill("input[name='currentDiscount.validToDate']", to_date)
        assert not pct
        page.fill("input[name='currentDiscount.absoluteDiscountAmount']", str(amt))
        page.click("input[type='submit']")

        log.info("discount code form submitted, getting response")
        page.wait_for_url(re.compile(r".*/discountList\.do.*"))
        if not page.get_by_text(code).is_visible():
            log.debug(str(page.content()))
            raise RuntimeError("Error assigning coupon; code not found on result page")
        return code

    def get_ticket_groups(self, ctx, event_id, content=None):
        """Gets ticket groups for an event"""
        if content is None:
            r = ctx.request.get(f"{ADMIN_URL}/event/eventDetails.do?id={event_id}")
            soup = BeautifulSoup(r.text(), features="html.parser")
        else:
            soup = BeautifulSoup(content, features="html.parser")
        ticketgroups = soup.find_all("td", class_="ticket-group")
        results = {}
        for tg in ticketgroups:
            groupname = tg.find("font").text
            m = re.search(r"ticketGroupId=(\d+)\&", str(tg))
            results[groupname] = m[1]
        return results

    def create_ticket_group_req_(self, ctx, event_id, group_name, group_desc):
        """Create a ticket group for an event"""
        referer = f"{ADMIN_URL}/event/newPackageGroup.do?eventId={event_id}"
        rg = ctx.request.get(referer)
        assert rg.status == 200

        drt_i = self.drt.get()
        data = {
            "z2DuplicateRequestToken": drt_i,
            "ticketPackageGroup.groupName": group_name,
            "ticketPackageGroup.description": group_desc,
            "ticketPackageGroup.startDate": "",
            "ticketPackageGroup.endDate": "",
        }
        r = ctx.request.post(
            f"{ADMIN_URL}/event/savePackageGroup.do",
            # Must set referer so the server knows which event this POST is for
            headers={"Referer": rg.url},
            form=data,
        )
        if r.status != 200:
            raise RuntimeError(f"{r.status}: {r.text()}")
        return r

    def assign_conditions_to_group(self, ctx, group_id, conds):
        """Assign a membership / income condition to a ticket group"""
        data = {
            "report": {
                "id": 22,
            },
            "searchCriteria": {
                "criteriaGroups": conds,
            },
            "extraConfig": {
                "EventTicketPackageGroupId": str(group_id),
            },
        }

        r = ctx.request.post(
            "https://protohaven.app.neoncrm.com/nx/admin/reports/nextgen/save",
            max_redirects=0,
            data=data,
            headers={
                "Referer": "https://protohaven.app.neoncrm.com/admin/reports/result"
            },
        )
        if r.status != 200:
            raise RuntimeError(
                "Report filter edit failed; expected code 200 OK, got " + str(r.status)
            )
        data = r.json()
        if not data.get("success"):
            raise RuntimeError(f"Report filter edit failed; response: {data}")
        return True

    def assign_price_to_group(  # pylint: disable=too-many-arguments
        self, ctx, event_id, group_id, price_name, amt, capacity
    ):
        """Assigns a specific price to a Neon ticket group"""
        referer = f"{ADMIN_URL}/event/newPackage.do?ticketGroupId={group_id}&eventId={event_id}"
        ag = ctx.request.get(referer)
        content = ag.text()
        if "Event Price" not in content:
            raise RuntimeError(
                f"BAD get group price creation page - {content[:128]}..."
            )

        # Submit report / condition
        # Must set referer so the server knows which event this POST is for
        drt_i = self.drt.get()
        data = {
            "z2DuplicateRequestToken": drt_i,
            "ticketPackage.sessionId": "",
            "ticketPackage.name": price_name,
            "ticketPackage.fee": str(amt),
            "ticketPackage.ticketPackageGroupid": (
                "" if group_id == "default" else str(group_id)
            ),
            "ticketPackage.capacity": str(capacity),
            "ticketPackage.advantageAmount": str(amt),
            "ticketPackage.advantageDescription": "",
            "ticketPackage.isUpto": "0",
            "ticketPackage.fixedAttendeeTotalPerReg": "1",
            "ticketPackage.description": "",
            "ticketPackage.webRegister": "on",
            "save": "+Submit+",
        }
        # log.debug(f"savePackage.do data={data}")
        r = ctx.request.post(
            f"{ADMIN_URL}/event/savePackage.do",
            max_redirects=0,
            form=data,
            headers={"Referer": ag.url},
        )
        soup = BeautifulSoup(r.text(), features="html.parser")
        errs = soup.find_all("div", class_="error")

        if r.status != 302 or errs:
            log.error(str(errs))

            raise RuntimeError(
                "Price creation failed; expected code 302, got " + str(r.status)
            )
        return True

    def upsert_ticket_group(self, ctx, event_id, group_name, group_desc):
        """Adds the ticket group to an event, if not already exists"""
        if group_name.lower() == "default":
            return "default"
        groups = self.get_ticket_groups(ctx, event_id)
        log.debug(f"Resolved ticket groups: {groups}")
        if group_name not in groups:
            log.debug("Group does not yet exist; creating")
            r = self.create_ticket_group_req_(ctx, event_id, group_name, group_desc)
            groups = self.get_ticket_groups(ctx, event_id, r.text())
        assert group_name in groups
        group_id = groups[group_name]
        return group_id

    def delete_all_prices_and_groups(self, ctx, event_id):
        """Deletes prices and groups belonging to a neon event"""
        assert event_id != "" and event_id is not None

        r = ctx.request.get(f"{ADMIN_URL}/event/eventDetails.do?id={event_id}")
        content = r.text()
        deletable_packages = list(
            set(re.findall(r"deletePackage\.do\?eventId=\d+\&id=(\d+)", content))
        )
        deletable_packages.sort()
        log.debug(f"Deletable pricing packages: {deletable_packages}")
        groups = set(re.findall(r"ticketGroupId=(\d+)", content))
        log.debug(f"Deletable groups: {groups}")

        for pkg_id in deletable_packages:
            log.debug(f"Delete pricing {pkg_id}")
            ctx.request.get(
                f"{ADMIN_URL}/event/deletePackage.do?eventId={event_id}&id={pkg_id}"
            )

        for group_id in groups:
            log.debug(f"Delete group {group_id}")
            ctx.request.get(
                f"{ADMIN_URL}/event/deletePackageGroup.do"
                f"?ticketGroupId={group_id}&eventId={event_id}"
            )

        # Re-run first price deletion as it's probably a default price
        # that must exist if there are conditional pricing applied
        if len(deletable_packages) > 0:
            log.debug(f"Re-delete pricing {deletable_packages[0]}")
            ctx.request.get(
                f"{ADMIN_URL}/event/deletePackage.do"
                f"?eventId={event_id}&id={deletable_packages[0]}"
            )

    def assign_pricing(  # pylint: disable=too-many-arguments
        self, event_id, price, seats, clear_existing=False, include_discounts=True
    ):
        """Assigns ticket pricing and quantities for a preexisting Neon event"""
        with sync_playwright() as p:
            # Launch a headless Firefox browser
            browser = p.firefox.launch(
                headless=True
            )  # Set headless=False for debugging
            ctx = browser.new_context()
            page = ctx.new_page()

            try:
                self.do_login(page)
            except PlaywrightTimeoutError:
                log.error(
                    "Timed out on first login attempt - trying again in 10 seconds..."
                )
                time.sleep(10.0)
                self.do_login(page)

            log.info("Clearing existing pricing (if any)...")
            if clear_existing:
                self.delete_all_prices_and_groups(ctx, event_id)

            log.info("Beginning price assignment")
            for p in pricing if include_discounts else pricing[:1]:
                log.info(f"Assign pricing: {p['name']}")
                group_id = self.upsert_ticket_group(
                    ctx, event_id, group_name=p["name"], group_desc=p["desc"]
                )
                if p.get("cond", None) is not None:
                    self.assign_conditions_to_group(ctx, group_id, p["cond"])

                # Some classes have so few seats that the ratio rounds down to zero
                # We just skip those here.
                qty = round(seats * p["qty_ratio"])
                if qty <= 0:
                    continue
                self.assign_price_to_group(
                    ctx,
                    event_id,
                    group_id,
                    p["price_name"],
                    round(price * p["price_ratio"]),
                    qty,
                )


def delete_event_unsafe(event_id):
    """Deletes an event in Neon"""
    log.warning(f"Deleting neon event {event_id}")
    assert event_id
    return delete("api_key3", f"/events/{event_id}")


def create_event(  # pylint: disable=too-many-arguments
    name,
    desc,
    start,
    end,
    category=Category.PROJECT_BASED_WORKSHOP,
    max_attendees=6,
    dry_run=True,
    published=True,
    registration=True,
    free=False,
):
    """Creates a new event in Neon CRM"""
    event = {
        "name": name,
        "summary": name,
        "maximumAttendees": max_attendees,
        "category": [
            {"id": category}
        ],  # 2025-10-22: Neon broke this; moved from single-instance dict to dict-list
        "publishEvent": published,
        "enableEventRegistrationForm": registration,
        "archived": False,
        "enableWaitListing": False,
        "createAccountsforAttendees": True,
        "eventDescription": desc,
        "eventDates": {
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "startTime": start.strftime("%-I:%M %p"),
            "endTime": end.strftime("%-I:%M %p"),
            "registrationOpenDate": datetime.datetime.now().isoformat(),
            "registrationCloseDate": (start - datetime.timedelta(hours=24)).isoformat(),
            "timeZone": {"id": "1"},
        },
        "financialSettings": {
            "feeType": "Free" if free else "MT_OA",
            "admissionFee": None,
            "ticketsPerRegistration": None,
            "fund": None,
            "taxDeductiblePortion": None,
        },
        "location": {
            "name": "Protohaven",
            "address": "214 N Trenton Ave.",
            "city": "Pittsburgh",
            "stateProvince": {
                "name": "Pennsylvania",
            },
            "zipCode": "15221",
        },
    }

    if dry_run:
        log.warning(
            f"DRY RUN {event['eventDates']['startDate']} "
            f"{event['eventDates']['startTime']} {event['name']}"
        )
        return None

    evt_request = get_connector().neon_request(
        get_config("neon/api_key3"),
        "POST",
        urllib.parse.urljoin(BASE_URL, "events"),
        data=json.dumps(event),
        headers={"content-type": "application/json"},
    )
    return evt_request["id"]


def active_or_future_membership_condition():
    """Generates a condition that requires an active or future membership for specific
    ticket prices to be available"""
    return {
        "id": 1,
        "searchCriteria": [
            {
                "fieldId": "120",
                "criteriaConditions": [
                    {
                        "operator": "9",
                        "value": "2,1",  # Active / Future
                    }
                ],
                "isAdvancedSearch": False,
                "fieldDisplay": "Account Current Membership Status",
                "dataType": 7,
                "operator": "",
                "valueDisplay": "Active or Future",
            }
        ],
    }


def income_condition(income_name, income_value):
    """Generates an "income condition" for making specific pricing of tickets available"""
    return {
        "id": 1,
        "searchCriteria": [
            {
                "fieldId": "account_custom_view.field78",
                "criteriaConditions": [
                    {
                        "operator": 1,
                        "value": str(income_value),
                    }
                ],
                "fieldDisplay": "Income Based Rate",
                "valueDisplay": income_name,
                "isAdvancedSearch": False,
            },
        ],
    }


def membership_condition(mem_names: list[str], mem_values: list[int]):
    """Generates a "membership condition" for making specific ticket prices available"""
    return {
        "id": 1,
        "searchCriteria": [
            {
                "fieldId": "98",
                "criteriaConditions": [
                    {
                        "operator": 9,
                        "value": ",".join(str(v) for v in mem_values),
                    }
                ],
                "fieldDisplay": "Membership Level",
                "valueDisplay": " or ".join(mem_names),
                "isAdvancedSearch": False,
            }
        ],
    }


pricing = [
    {
        "name": "default",
        "desc": "",
        "price_ratio": 1.0,
        "qty_ratio": 1.0,
        "price_name": "Single Registration",
    },
    {
        "name": "ELI - Price",
        "desc": "70% Off",
        "cond": [
            active_or_future_membership_condition(),
            income_condition("Extremely Low Income - 70%", 43),
        ],
        "price_ratio": 0.3,
        "qty_ratio": 0.25,
        "price_name": "AMP Rate",
    },
    {
        "name": "VLI - Price",
        "desc": "50% Off",
        "cond": [
            active_or_future_membership_condition(),
            income_condition("Very Low Income - 50%", 42),
        ],
        "price_ratio": 0.5,
        "qty_ratio": 0.25,
        "price_name": "AMP Rate",
    },
    {
        "name": "LI - Price",
        "desc": "20% Off",
        "cond": [
            active_or_future_membership_condition(),
            income_condition("Low Income - 20%", 41),
        ],
        "price_ratio": 0.8,
        "qty_ratio": 0.5,
        "price_name": "AMP Rate",
    },
    {
        "name": "Member Discount",
        "desc": "20% Off",
        "cond": [
            active_or_future_membership_condition(),
            membership_condition(
                Member.MEMBERSHIP_DISCOUNT_LEVELS,
                # These are IDs of the membership levels. For reference, see
                # https://protohaven.app.neoncrm.com/np/admin/systemsetting/membershipHome.do
                # And look at the suffix of the `Edit` urls.
                # These must be listed in order with the strings above.
                [1, 27, 26, 6, 24, 2, 25, 3],
            ),
        ],
        "price_ratio": 0.8,
        "qty_ratio": 1.0,
        "price_name": "Member Rate",
    },
    {
        "name": "Instructor Discount",
        "desc": "50% Off",
        "cond": [
            active_or_future_membership_condition(),
            membership_condition(["Instructor"], [9]),
        ],
        "price_ratio": 0.5,
        "qty_ratio": 1.0,
        "price_name": "Instructor Rate",
    },
]
