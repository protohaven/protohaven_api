"""Helper methods for the code in integrations.neon"""
import datetime
import json
import logging
import re
import time
import urllib

from bs4 import BeautifulSoup

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector
from protohaven_api.integrations.data.neon import ADMIN_URL, URL_BASE, Category

log = logging.getLogger("integrations.neon_base")


def paginated_fetch(api_key, path, params=None):
    """Issue GET requests against Neon's V2 API, yielding all results across
    all result pages"""
    current_page = 0
    total_pages = 1
    result_field = path.split("/")[-1]
    params = params or {}
    while current_page < total_pages:
        params["currentPage"] = current_page
        url = f"{URL_BASE}{path}?{urllib.parse.urlencode(params)}"
        log.debug(url)
        content = get_connector().neon_request(
            get_config(f"neon/{api_key}"), url, "GET"
        )
        if isinstance(content, list):
            raise RuntimeError(content)
        total_pages = content["pagination"]["totalPages"]
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
        "outputFields": output_fields,
        "pagination": {"currentPage": cur, "pageSize": 50, **(pagination or {})},
    }
    total = 1
    while cur < total:
        content = get_connector().neon_request(
            get_config("neon/api_key2"),
            f"{URL_BASE}/{typ}/search",
            "POST",
            body=json.dumps(data),
            headers={"content-type": "application/json"},
        )
        if content.get("searchResults") is None or content.get("pagination") is None:
            raise RuntimeError(f"Search failed: {content}")

        total = content["pagination"]["totalPages"]
        cur += 1
        data["pagination"]["currentPage"] = cur
        yield from content["searchResults"]


def fetch_account(account_id, required=False):
    """Fetches account information for a specific user in Neon.
    Raises RuntimeError if an error is returned from the server, or None
    if the account is not found.
    Second return value is True if the account is for a company, False otherwise
    """
    content = get("api_key1", f"/accounts/{account_id}")
    if isinstance(content, list):
        raise RuntimeError(content)
    if content is None and required:
        raise RuntimeError(f"Account not found: {account_id}")
    if content is None and not required:
        return None
    return (
        (content.get("individualAccount") or content.get("companyAccount") or None),
        ("companyAccount" in content),
    )


def get(api_key, path):
    """Send an HTTP GET request"""
    assert path.startswith("/")
    return get_connector().neon_request(get_config(f"neon/{api_key}"), URL_BASE + path)


def patch(api_key, path, body):
    """Send an HTTP PATCH request"""
    assert path.startswith("/")
    return get_connector().neon_request(
        get_config(f"neon{api_key}"),
        URL_BASE + path,
        "PATCH",
        body=json.dumps(body),
        headers={"content-type": "application/json"},
    )


def put(api_key, path, body):
    """Send an HTTP PUT request"""
    assert path.startswith("/")
    return get_connector().neon_request(
        get_config(f"neon{api_key}"),
        URL_BASE + path,
        "PUT",
        body=json.dumps(body),
        headers={"content-type": "application/json"},
    )


def patch_account(account_id, data):
    """Patch an existing account via Neon V2 API"""
    _, is_company = fetch_account(account_id, required=True)
    return patch(
        get_config("neon/api_key2"),
        f"{URL_BASE}/accounts/{account_id}",
        {"companyAccount": data} if is_company else {"individualAccount": data},
    )


def get_custom_field(account_id, field_id):
    """Get the value of a single custom field from Neon"""
    acc, _ = fetch_account(account_id, required=True)
    for cf in acc.get("accountCustomFields", []):
        if cf["name"] == field_id:
            return cf.get("value") or cf.get("optionValues")
    return []


def set_custom_fields(account_id, *fields):
    """Set any custom field for a user in Neon"""
    return patch_account(
        account_id,
        {
            "accountCustomFields": [
                {"id": field_id, "optionValues": value}
                if isinstance(value, list)
                else {"id": field_id, "value": value}
                for field_id, value in fields
            ]
        },
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
        self.s = get_connector().neon_session()
        self.drt = DuplicateRequestToken()
        self._do_login(get_config("neon/login_user"), get_config("neon/login_pass"))

    def _do_login(self, user, passwd):
        csrf = self._get_csrf()
        log.debug(f"CSRF: {csrf}")

        # Submit login info to initial login page
        r = self.s.post(
            "https://app.neonsso.com/login",
            data={"_token": csrf, "email": user, "password": passwd},
        )
        assert r.status_code == 200

        # Select Neon SSO and go through the series of SSO redirects to properly set cookies
        r = self.s.get("https://app.neoncrm.com/np/ssoAuth")
        dec = r.content.decode("utf8")
        if "Mission Control Dashboard" not in dec:
            raise RuntimeError(dec)

    def _get_csrf(self):
        rlogin = self.s.get("https://app.neonsso.com/login")
        assert rlogin.status_code == 200
        csrf = None
        soup = BeautifulSoup(rlogin.content.decode("utf8"), features="html.parser")
        for m in soup.head.find_all("meta"):
            if m.get("name") == "csrf-token":
                csrf = m["content"]
        return csrf

    def soft_search(self, keyword):
        """Search based on a keyword - matches email, first/last names etc"""
        r = self.s.get(
            f"https://protohaven.app.neoncrm.com/nx/top-search/search?keyword={keyword}"
        )
        assert r.status_code == 200
        content = json.loads(r.content.decode("utf8"))
        return content

    def create_single_use_abs_event_discount(self, code, amt):
        """Creates an absolute discount, usable once"""
        return self._post_discount(
            self.TYPE_EVENT_DISCOUNT, code=code, pct=False, amt=amt
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

    def assign_price_to_group(
        self, event_id, group_id, price_name, amt, capacity
    ):  # pylint: disable=too-many-arguments
        """Assigns a specific price to a Neon ticket group"""
        referer = f"{ADMIN_URL}/event/newPackage.do?ticketGroupId={group_id}&eventId={event_id}"
        ag = self.s.get(referer)
        content = ag.content.decode("utf8")
        if "Event Price" not in content:
            raise RuntimeError("BAD get group price creation page")

        # Submit report / condition
        # Must set referer so the server knows which event this POST is for
        self.s.headers.update({"Referer": ag.url})
        drt_i = self.drt.get()
        data = {
            "z2DuplicateRequestToken": drt_i,
            "ticketPackage.sessionId": "",
            "ticketPackage.name": price_name,
            "ticketPackage.fee": str(amt),
            "ticketPackage.ticketPackageGroupid": ""
            if group_id == "default"
            else str(group_id),
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
            raise RuntimeError(
                "Price creation failed; expected code 302 FOUND, got "
                + str(r.status_code)
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
            "feeType": "MT_OA",
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
        f"{URL_BASE}/events",
        "POST",
        body=json.dumps(event),
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
                    ],
                    [1, 27, 26],
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
