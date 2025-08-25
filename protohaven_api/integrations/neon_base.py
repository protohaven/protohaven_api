"""Helper methods for the code in integrations.neon"""

import datetime
import json
import logging
import re
import time
import urllib

import pyotp
from bs4 import BeautifulSoup

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

    def __init__(self, autologin=True):
        self.s = get_connector().neon_session()
        self.drt = DuplicateRequestToken()
        self.totp = pyotp.TOTP(get_config("neon/login_otp_code"))
        if autologin:
            self.do_login(get_config("neon/login_user"), get_config("neon/login_pass"))

    def do_login(self, user, passwd):
        """Performs user login, handling second factor OTP if needed"""
        csrf = self._get_csrf()
        log.debug(f"CSRF: {csrf}")

        # Submit login info to initial login page
        r = self.s.post(
            f"{SSO_URL}/login",
            data={"_token": csrf, "email": user, "password": passwd},
        )
        if r.status_code != 200:
            raise RuntimeError("do_login HTTP {r.status_code}: {r.content}")

        content = r.content.decode("utf8")
        if "2-Step Verification" in content:
            m = re.search(r'name="_token" value="([^"]+)"', content)
            if not m:
                raise RuntimeError(
                    f"Could not extract MFA token from 2 step verification page:\n{content}"
                )
            log.debug(f"Using mfa token {m.group(1)}")
            r = self.s.post(
                f"{SSO_URL}/mfa",
                data={"_token": m.group(1), "mfa_code": str(self.totp.now())},
            )

        assert "Log Out" in r.content.decode("utf8")

        # Select Neon SSO and go through the series of SSO redirects to properly set cookies
        r = self.s.get("https://app.neoncrm.com/np/ssoAuth")
        dec = r.content.decode("utf8")
        if "Mission Control Dashboard" not in dec:
            raise RuntimeError(dec)

    def _get_csrf(self):
        rlogin = self.s.get(f"{SSO_URL}/login")
        if rlogin.status_code != 200:
            raise RuntimeError(f"_get_csrf HTTP {rlogin.status_code}: {rlogin.content}")
        csrf = None
        soup = BeautifulSoup(rlogin.content.decode("utf8"), features="html.parser")
        for m in soup.head.find_all("meta"):
            if m.get("name") == "csrf-token":
                csrf = m["content"]
        return csrf

    def create_single_use_abs_event_discount(
        self, code, amt, from_date=None, to_date=None
    ):
        """Creates an absolute discount, usable once"""
        return self._post_discount(
            self.TYPE_EVENT_DISCOUNT,
            code=code,
            pct=False,
            amt=amt,
            from_date=from_date,
            to_date=to_date,
        )

    def _post_discount(  # pylint: disable=too-many-arguments
        self,
        typ,
        code,
        pct,
        amt,
        from_date="11/19/2023",
        to_date="11/21/2024",
        max_uses=1,
    ):
        if from_date is None:
            from_date = tznow()
        if to_date is None:
            to_date = from_date + datetime.timedelta(days=90)
        from_date = from_date.strftime("%m/%d/%Y")
        to_date = to_date.strftime("%m/%d/%Y")

        # We must appear to be coming from the specific discount settings page (Event or Membership)
        referer = (
            f"{ADMIN_URL}/systemsetting/"
            + f"newCouponCodeDiscount.do?sellingItemType={typ}&discountType=1"
        )
        rg = self.s.get(referer)
        assert rg.status_code == 200

        # Must set referer so the server knows which "selling item type" this POST is for
        self.s.headers.update({"Referer": rg.url})
        drt_i = self.drt.get()
        data = {
            "z2DuplicateRequestToken": drt_i,
            "priceOff": "coupon",
            "currentDiscount.couponCode": code,
            "currentDiscount.sellingItemId": "",
            "currentDiscount.maxUses": max_uses,
            "currentDiscount.validFromDate": from_date,
            "currentDiscount.validToDate": to_date,
            "currentDiscount.percentageValue": 1 if pct else 0,
            "submit": " Save ",
        }
        if typ == self.TYPE_EVENT_DISCOUNT:
            data["currentDiscount.eventTicketPackageGroupId"] = ""

        if pct:
            data["currentDiscount.percentageDiscountAmount"] = amt
        else:
            data["currentDiscount.absoluteDiscountAmount"] = amt

        r = self.s.post(
            f"{ADMIN_URL}/systemsetting/couponCodeDiscountSave.do",
            allow_redirects=False,
            data=data,
        )

        log.debug(f"Response {r.status_code} {r.headers}")

        if not "discountList.do" in r.headers.get("Location", ""):
            raise RuntimeError(
                "Failed to land on appropriate page - wanted discountList.do, got "
                + r.headers.get("Location", "")
            )
        return code

    def get_ticket_groups(self, event_id, content=None):
        """Gets ticket groups for an event"""
        if content is None:
            r = self.s.get(f"{ADMIN_URL}/event/eventDetails.do?id={event_id}")
            soup = BeautifulSoup(r.content.decode("utf8"), features="html.parser")
        else:
            soup = BeautifulSoup(content.decode("utf8"), features="html.parser")
        ticketgroups = soup.find_all("td", class_="ticket-group")
        results = {}
        for tg in ticketgroups:
            groupname = tg.find("font").text
            m = re.search(r"ticketGroupId=(\d+)\&", str(tg))
            results[groupname] = m[1]
        return results

    def create_ticket_group_req_(self, event_id, group_name, group_desc):
        """Create a ticket group for an event"""
        # We must appear to be coming from the package grup creation page
        referer = f"{ADMIN_URL}/event/newPackageGroup.do?eventId={event_id}"
        rg = self.s.get(referer)
        assert rg.status_code == 200

        # Must set referer so the server knows which event this POST is for
        self.s.headers.update({"Referer": rg.url})
        drt_i = self.drt.get()
        data = {
            "z2DuplicateRequestToken": drt_i,
            "ticketPackageGroup.groupName": group_name,
            "ticketPackageGroup.description": group_desc,
            "ticketPackageGroup.startDate": "",
            "ticketPackageGroup.endDate": "",
        }
        r = self.s.post(
            f"{ADMIN_URL}/event/savePackageGroup.do",
            allow_redirects=True,
            data=data,
        )
        if r.status_code != 200:
            raise RuntimeError(f"{r.status_code}: {r.content}")
        return r

    def assign_condition_to_group(self, event_id, group_id, cond):
        """Assign a membership / income condition to a ticket group"""
        # Load report setup page
        referer = f"{ADMIN_URL}/v2report/validFieldsList.do"
        referer += "?reportId=22"
        referer += "&searchCriteriaId="
        referer += f"&EventTicketPackageGroupId={group_id}&eventId={event_id}"
        ag = self.s.get(referer)
        content = ag.content.decode("utf8")

        if "All Accounts Report" not in content:
            raise RuntimeError("Bad GET report setup page:", content)

        # Submit report / condition
        # Must set referer so the server knows which event this POST is for
        self.s.headers.update({"Referer": ag.url})
        drt_i = self.drt.get()
        data = {
            "z2DuplicateRequestToken": drt_i,
            "saveandsearchFlag": "search",
            "actionFrom": "validColumn",
            "savedSearchCriteria": json.dumps(cond),
            "savedSearchFurtherCriteria": [],
            "searchFurtherFlag": 0,
            "searchFurtherType": 0,
            "searchType": 0,
            "savedSearchColumn": [
                "65",
                "377",
                "19",
                "117",
                "26",
                "27",
                "28",
                "9",
                "429",
                "439",
                "443",
                "437",
            ],  # What's this??
            "savedColumnToDefault": "",
            "comeFrom": None,
        }
        r = self.s.post(
            f"{ADMIN_URL}/report/reportFilterEdit.do",
            allow_redirects=False,
            data=data,
        )
        if r.status_code != 302:
            raise RuntimeError(
                "Report filter edit failed; expected code 302 FOUND, got "
                + str(r.status_code)
            )

        # Do initial report execution
        self.s.headers.update({"Referer": r.url})
        r = self.s.get(
            f"{ADMIN_URL}/report/searchCriteriaSearch.do"
            "?actionFrom=validColumn&searchFurtherType=0&searchType=0&comeFrom=null"
        )
        content = r.content.decode("utf8")
        if "Return to Event Detail Page" not in content:
            raise RuntimeError("Bad GET report setup page:", content)

        # Set the search details
        self.s.headers.update({"Referer": r.url})
        r = self.s.get(
            f"{ADMIN_URL}/systemsetting/eventTicketGroupConditionSave.do?ticketGroupId={group_id}",
            allow_redirects=False,
        )
        if r.status_code != 302:
            raise RuntimeError(f"{r.status_code}: {r.content}")
        return True

    def assign_price_to_group(  # pylint: disable=too-many-arguments
        self, event_id, group_id, price_name, amt, capacity
    ):
        """Assigns a specific price to a Neon ticket group"""
        referer = f"{ADMIN_URL}/event/newPackage.do?ticketGroupId={group_id}&eventId={event_id}"
        ag = self.s.get(referer)
        content = ag.content.decode("utf8")
        if "Event Price" not in content:
            raise RuntimeError(
                f"BAD get group price creation page - {content[:128]}..."
            )

        # Submit report / condition
        # Must set referer so the server knows which event this POST is for
        self.s.headers.update({"Referer": ag.url})
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
            "ticketPackage.description": "",
            "ticketPackage.webRegister": "on",
            "save": " Submit ",
        }
        r = self.s.post(
            f"{ADMIN_URL}/event/savePackage.do",
            allow_redirects=False,
            data=data,
        )
        if r.status_code != 302:
            log.error(r.content.decode("utf8"))
            raise RuntimeError(
                "Price creation failed; expected code 302, got " + str(r.status_code)
            )
        return True

    def upsert_ticket_group(self, event_id, group_name, group_desc):
        """Adds the ticket group to an event, if not already exists"""
        if group_name.lower() == "default":
            return "default"
        groups = self.get_ticket_groups(event_id)
        if group_name not in groups:
            log.debug("Group does not yet exist; creating")
            r = self.create_ticket_group_req_(event_id, group_name, group_desc)
            groups = self.get_ticket_groups(event_id, r.content)
        assert group_name in groups
        group_id = groups[group_name]
        return group_id

    def delete_all_prices_and_groups(self, event_id):
        """Deletes prices and groups belonging to a neon event"""
        assert event_id != "" and event_id is not None

        r = self.s.get(f"{ADMIN_URL}/event/eventDetails.do?id={event_id}")
        content = r.content.decode("utf8")
        deletable_packages = list(
            set(re.findall(r"deletePackage\.do\?eventId=\d+\&id=(\d+)", content))
        )
        deletable_packages.sort()
        log.debug(deletable_packages)
        groups = set(re.findall(r"ticketGroupId=(\d+)", content))
        log.debug(groups)

        for pkg_id in deletable_packages:
            log.debug(f"Delete pricing {pkg_id}")
            self.s.get(
                f"{ADMIN_URL}/event/deletePackage.do?eventId={event_id}&id={pkg_id}"
            )

        for group_id in groups:
            log.debug(f"Delete group {group_id}")
            self.s.get(
                f"{ADMIN_URL}/event/deletePackageGroup.do"
                f"?ticketGroupId={group_id}&eventId={event_id}"
            )

        # Re-run first price deletion as it's probably a default price
        # that must exist if there are conditional pricing applied
        if len(deletable_packages) > 0:
            log.debug(f"Re-delete pricing {deletable_packages[0]}")
            self.s.get(
                f"{ADMIN_URL}/event/deletePackage.do"
                f"?eventId={event_id}&id={deletable_packages[0]}"
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
        "category": {"id": category},
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


def income_condition(income_name, income_value):
    """Generates an "income condition" for making specific pricing of tickets available"""
    return {
        "name": "account_custom_view.field78",
        "displayName": "Income Based Rates",
        "groupId": "220",
        "savedGroup": "1",
        "operator": "1",
        "operatorName": "Equal",
        "optionName": income_name,
        "optionValue": str(income_value),
    }


def membership_condition(mem_names, mem_values):
    """Generates a "membership condition" for making specific ticket prices available"""
    stvals = [f"'{v}'" for v in mem_values]
    stvals = f"({','.join(stvals)})"
    return {
        "name": "membership_listing.membershipId",
        "displayName": "Membership+Level",
        "groupId": "55",
        "savedGroup": "1",
        "operator": "9",
        "operatorName": "In Range Of",
        "optionName": " or ".join(mem_names),
        "optionValue": stvals,
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
        "desc": "70% Of",
        "cond": [[income_condition("Extremely Low Income - 70%", 43)]],
        "price_ratio": 0.3,
        "qty_ratio": 0.25,
        "price_name": "AMP Rate",
    },
    {
        "name": "VLI - Price",
        "desc": "50% Of",
        "cond": [[income_condition("Very Low Income - 50%", 42)]],
        "price_ratio": 0.5,
        "qty_ratio": 0.25,
        "price_name": "AMP Rate",
    },
    {
        "name": "LI - Price",
        "desc": "20% Of",
        "cond": [[income_condition("Low Income - 20%", 41)]],
        "price_ratio": 0.8,
        "qty_ratio": 0.5,
        "price_name": "AMP Rate",
    },
    {
        "name": "Member Discount",
        "desc": "20% Of",
        "cond": [
            [
                membership_condition(
                    [
                        "General+Membership",
                        "Primary+Family+Membership",
                        "Additional+Family+Membership",
                        "Company Membership",
                        "Corporate Membership",
                        "Weekend Membership",
                        "Weeknight Membership",
                        "Non-profit Membership",
                    ],
                    # These are IDs of the membership types. For reference, see
                    # https://protohaven.app.neoncrm.com/np/admin/systemsetting/membershipHome.do
                    # And look at the suffix of the `Edit` urls.
                    # These must be listed in order with the strings above.
                    [1, 27, 26, 6, 24, 2, 25, 3],
                )
            ]
        ],
        "price_ratio": 0.8,
        "qty_ratio": 1.0,
        "price_name": "Member Rate",
    },
    {
        "name": "Instructor Discount",
        "desc": "50% Of",
        "cond": [[membership_condition(["Instructor"], [9])]],
        "price_ratio": 0.5,
        "qty_ratio": 1.0,
        "price_name": "Instructor Rate",
    },
]
