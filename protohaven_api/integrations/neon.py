"# Acknowledge always overwrites the previous state" " Neon CRM integration methods" ""
import datetime
import json
import logging
import re
import time
import urllib
from functools import cache

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector

log = logging.getLogger("integrations.neon")


def cfg(param):
    """Load neon configuration"""
    return get_config()["neon"][param]


TEST_MEMBER = 1727
GROUP_ID_CLEARANCES = 1
CUSTOM_FIELD_CLEARANCES = 75
CUSTOM_FIELD_INTEREST = 148
CUSTOM_FIELD_DISCORD_USER = 150
CUSTOM_FIELD_WAIVER_ACCEPTED = 151
WAIVER_FMT = "version {version} on {accepted}"
WAIVER_REGEX = r"version (.+?) on (.*)"
URL_BASE = "https://api.neoncrm.com/v2"


def fetch_published_upcoming_events(back_days=7):
    """Load upcoming events from Neon CRM, with `back_days` of trailing event data.
    Note that querying is done based on the end date so multi-week intensives
    can still appear even if they started earlier than `back_days`."""
    q_params = {
        "endDateAfter": (
            datetime.datetime.now() - datetime.timedelta(days=back_days)
        ).strftime("%Y-%m-%d"),
        "publishedEvent": True,
        "archived": False,
        "pagination": {
            "currentPage": 0,
        },
    }
    current_page = 0
    total_pages = 1
    while current_page < total_pages:
        q_params["pagination"]["currentPage"] = current_page
        encoded_params = urllib.parse.urlencode(q_params)
        _, content = get_connector().neon_request(
            cfg("api_key1"),
            "https://api.neoncrm.com/v2/events?" + encoded_params,
            "GET",
        )
        content = json.loads(content)
        total_pages = content["pagination"]["totalPages"]
        for cls in content["events"]:
            yield cls
        current_page += 1


def fetch_events(after=None, before=None, published=True):
    """Load events from Neon CRM"""
    q_params = {"publishedEvent": published}
    if after is not None:
        q_params["startDateAfter"] = after.strftime("%Y-%m-%d")
    if before is not None:
        q_params["startDateBefore"] = before.strftime("%Y-%m-%d")
    encoded_params = urllib.parse.urlencode(q_params)
    _, content = get_connector().neon_request(
        cfg("api_key1"), "https://api.neoncrm.com/v2/events?" + encoded_params, "GET"
    )
    content = json.loads(content)
    if isinstance(content, list):
        raise RuntimeError(content)
    return content["events"]


def fetch_event(event_id):
    """Fetch data on an individual (legacy) event in Neon"""
    resp, content = get_connector().neon_request(
        cfg("api_key1"), f"https://api.neoncrm.com/v2/events/{event_id}"
    )
    if resp.status != 200:
        raise RuntimeError(f"fetch_event({event_id}) {resp.status}: {content}")
    return json.loads(content)


def fetch_registrations(event_id):
    """Fetch registrations for a specific Neon event"""
    resp, content = get_connector().neon_request(
        cfg("api_key1"),
        f"https://api.neoncrm.com/v2/events/{event_id}/eventRegistrations",
    )
    if resp.status != 200:
        raise RuntimeError(f"fetch_registrations({event_id}) {resp.status}: {content}")
    content = json.loads(content)
    if isinstance(content, list):
        raise RuntimeError(content)
    if content["pagination"]["totalPages"] > 1:
        raise RuntimeError("TODO implement pagination for fetch_attendees()")
    return content["eventRegistrations"] or []


def fetch_tickets(event_id):
    """Fetch ticket information for a specific Neon event"""
    resp, content = get_connector().neon_request(
        cfg("api_key1"), f"https://api.neoncrm.com/v2/events/{event_id}/tickets"
    )
    if resp.status != 200:
        raise RuntimeError(f"fetch_tickets({event_id}) {resp.status}: {content}")
    content = json.loads(content)
    if isinstance(content, list):
        return content
    raise RuntimeError(content)


def fetch_attendees(event_id):
    """Fetch attendee data on an individual (legacy) event in Neon"""
    current_page = 0
    total_pages = 1
    while current_page < total_pages:
        url = f"https://api.neoncrm.com/v2/events/{event_id}/attendees?currentPage={current_page}"
        log.debug(url)
        resp, content = get_connector().neon_request(
            cfg("api_key1"),
            url,
            "GET",
        )
        if resp.status != 200:
            raise RuntimeError(f"fetch_attendees({event_id}) {resp.status}: {content}")
        content = json.loads(content)
        if isinstance(content, list):
            raise RuntimeError(content)
        if content["pagination"]["totalResults"] == 0:
            return  # basically an empty yield
        total_pages = content["pagination"]["totalPages"]
        log.debug(content)
        for a in content["attendees"]:
            yield a
        current_page += 1


@cache
def fetch_clearance_codes():
    """Fetch all the possible clearance codes that can be used in Neon"""
    resp, content = get_connector().neon_request(
        cfg("api_key1"), f"{URL_BASE}/customFields/{CUSTOM_FIELD_CLEARANCES}", "GET"
    )
    assert resp.status == 200
    return json.loads(content)["optionValues"]


def get_user_clearances(account_id):
    """Fetch clearances for an individual user in Neon"""
    # Should probably cache this a bit
    id_to_code = {c["id"]: c["code"] for c in fetch_clearance_codes()}
    acc = fetch_account(account_id)
    if acc is None:
        raise RuntimeError("Account not found")
    custom = acc.get("individualAccount")
    if custom is None:
        custom = acc.get("companyAccount")
    if custom is None:
        return []
    custom = custom.get("accountCustomFields", [])
    for cf in custom:
        if cf["name"] == "Clearances":
            return [id_to_code.get(v["id"]) for v in cf["optionValues"]]
    return []


def set_clearance_codes(codes):
    """Set all the possible clearance codes that can be used in Neon
    DANGER: Get clearance codes and extend that list, otherwise
    you risk losing clearance data for users.
    """
    data = {
        "groupId": GROUP_ID_CLEARANCES,
        "id": CUSTOM_FIELD_CLEARANCES,
        "displayType": "Checkbox",
        "name": "Clearances",
        "dataType": "Integer",
        "component": "Account",
        "optionValues": codes,
    }
    resp, content = get_connector().neon_request(
        cfg("api_key1"),
        f"{URL_BASE}/customFields/{CUSTOM_FIELD_CLEARANCES}",
        "PUT",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    print("PUT", resp.status, content)


def set_custom_field(user_id, data):
    """Set any custom field for a user in Neon"""
    data = {
        "individualAccount": {
            "accountCustomFields": [data],
        }
    }
    resp, content = get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/{user_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    print("PATCH", resp.status, content)


def set_interest(user_id, interest: str):
    """Assign interest to user custom field"""
    return set_custom_field(user_id, {"id": CUSTOM_FIELD_INTEREST, "value": interest})


def set_discord_user(user_id, discord_user: str):
    """Sets the discord user used by this user"""
    return set_custom_field(
        user_id, {"id": CUSTOM_FIELD_DISCORD_USER, "value": discord_user}
    )


def set_clearances(user_id, codes):
    """Sets all clearances for a specific user - company or individual"""
    code_to_id = {c["code"]: c["id"] for c in fetch_clearance_codes()}
    ids = [code_to_id[c] for c in codes]

    # Need to confirm whether the user is an individual or company account
    m = fetch_account(user_id)
    if m is None:
        return None

    data = {
        "accountCustomFields": [
            {"id": CUSTOM_FIELD_CLEARANCES, "optionValues": [{"id": i} for i in ids]}
        ],
    }

    if m.get("individualAccount"):
        data = {"individualAccount": data}
    elif m.get("companyAccount"):
        data = {"companyAccount": data}
    else:
        raise RuntimeError("Unknown account type for " + str(user_id))

    resp, content = get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/{user_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    print("PATCH", resp.status, content)
    return resp, content


def fetch_account(account_id):
    """Fetches account information for a specific user in Neon.
    Raises RuntimeError if an error is returned from the server"""
    _, content = get_connector().neon_request(
        cfg("api_key1"), f"https://api.neoncrm.com/v2/accounts/{account_id}"
    )
    if content == b"":
        raise RuntimeError(f"No member found for account_id {account_id}")
    content = json.loads(content)
    if isinstance(content, list):
        raise RuntimeError(content)
    return content


def search_member_by_name(firstname, lastname):
    """Lookup a user by first and last name"""
    data = {
        "searchFields": [
            {
                "field": "First Name",
                "operator": "EQUAL",
                "value": firstname.strip(),
            },
            {
                "field": "Last Name",
                "operator": "EQUAL",
                "value": lastname.strip(),
            },
        ],
        "outputFields": [
            "Account ID",
            "Email 1",
        ],
        "pagination": {
            "currentPage": 0,
            "pageSize": 1,
        },
    }
    resp, content = get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/search",
        "POST",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    if resp.status != 200:
        raise RuntimeError(f"Error {resp.status}: {content}")
    content = json.loads(content)
    if content.get("searchResults") is None:
        raise RuntimeError(f"Search for {firstname} {lastname} failed: {content}")
    return content["searchResults"][0] if len(content["searchResults"]) > 0 else None


def search_member(email):
    """Lookup a user by their email"""
    data = {
        "searchFields": [
            {
                "field": "Email",
                "operator": "EQUAL",
                "value": email,
            }
        ],
        "outputFields": [
            "Account ID",
            "First Name",
            "Last Name",
            "Account Current Membership Status",
            "Membership Level",
            CUSTOM_FIELD_CLEARANCES,
            CUSTOM_FIELD_DISCORD_USER,
            CUSTOM_FIELD_WAIVER_ACCEPTED,
        ],
        "pagination": {
            "currentPage": 0,
            "pageSize": 1,
        },
    }
    resp, content = get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/search",
        "POST",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    if resp.status != 200:
        raise RuntimeError(f"Error {resp.status}: {content}")
    content = json.loads(content)
    if content.get("searchResults") is None:
        raise RuntimeError(f"Search for {email} failed: {content}")
    return content["searchResults"][0] if len(content["searchResults"]) > 0 else None


def get_members_with_role(role, extra_fields):
    """Fetch all members with a specific assigned role (e.g. all shop techs)"""
    # Do we need to search email 2 and 3 as well?
    cur = 0
    data = {
        "searchFields": [
            {
                "field": "85",
                "operator": "CONTAIN",
                "value": role["id"],
            }
        ],
        "outputFields": ["Account ID", "First Name", "Last Name", *extra_fields],
        "pagination": {
            "currentPage": cur,
            "pageSize": 50,
        },
    }
    total = 1
    while cur < total:
        resp, content = get_connector().neon_request(
            cfg("api_key2"),
            f"{URL_BASE}/accounts/search",
            "POST",
            body=json.dumps(data),
            headers={"content-type": "application/json"},
        )
        if resp.status != 200:
            raise RuntimeError(f"Error {resp.status}: {content}")
        content = json.loads(content)
        if content.get("searchResults") is None or content.get("pagination") is None:
            raise RuntimeError(f"Search for {role} failed: {content}")

        # print(f"======= Page {cur} of {total} (size {len(content['searchResults'])}) =======")
        total = content["pagination"]["totalPages"]
        cur += 1
        data["pagination"]["currentPage"] = cur

        for r in content["searchResults"]:
            yield r


class DuplicateRequestToken:  # pylint: disable=too-few-public-methods
    """A quick little emulator of the duplicat request token behavior on Neon's site"""

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

    def __init__(self, user, passwd):
        self.s = get_connector().neon_session()
        self.drt = DuplicateRequestToken()
        self._do_login(user, passwd)

    def _do_login(self, user, passwd):
        csrf = self._get_csrf()
        print("CSRF:", csrf)

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
            "https://protohaven.app.neoncrm.com/np/admin/systemsetting/"
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
            "https://protohaven.app.neoncrm.com/np/admin/systemsetting/couponCodeDiscountSave.do",
            allow_redirects=False,
            data=data,
        )

        # print(r)
        # print("Request")
        # print(r.request.url)
        # print(r.request.body)
        # print(r.request.headers)

        print("Response")
        print(r.status_code)
        print(r.headers)

        if not "discountList.do" in r.headers.get("Location", ""):
            raise RuntimeError(
                "Failed to land on appropriate page - wanted discountList.do, got "
                + r.headers.get("Location", "")
            )
        return code


def set_event_scheduled_state(neon_id, scheduled=True):
    """Publishes or unpublishes an event in Neon"""
    data = {
        "publishEvent": scheduled,
        "enableEventRegistrationForm": scheduled,
        "archived": not scheduled,
        "enableWaitListing": scheduled,
    }
    resp, content = get_connector().neon_request(
        cfg("api_key3"),
        f"{URL_BASE}/events/{neon_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    if resp.status != 200:
        raise RuntimeError(f"Error {resp.status}: {content}")
    content = json.loads(content)
    return content["id"]


def create_coupon_code(code, amt):
    """Creates a coupon code for a specific absolute amount"""
    n = NeonOne(cfg("login_user"), cfg("login_pass"))
    return n.create_single_use_abs_event_discount(code, amt)


def soft_search(keyword):
    """Creates a coupon code for a specific absolute amount"""
    n = NeonOne(cfg("login_user"), cfg("login_pass"))
    return n.soft_search(keyword)


def set_waiver_status(user_id, new_status):
    """Overwrites existing waiver status information on an account"""
    data = {
        "accountCustomFields": [
            {"id": CUSTOM_FIELD_WAIVER_ACCEPTED, "value": new_status}
        ],
    }
    # Need to confirm whether the user is an individual or company account
    m = fetch_account(user_id)
    if m is None:
        raise RuntimeError("Failed to resolve account type for waiver application")

    if m.get("individualAccount"):
        data = {"individualAccount": data}
    elif m.get("companyAccount"):
        data = {"companyAccount": data}
    else:
        raise RuntimeError("Unknown account type for " + str(user_id))

    resp, content = get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/{user_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    print("PATCH", resp.status, content)
    return resp, content


def update_waiver_status(  # pylint: disable=too-many-arguments
    user_id,
    waiver_status,
    ack,
    now=None,
    current_version=cfg("waiver_published_date"),
    expiration_days=cfg("waiver_expiration_days"),
):
    """Update the liability waiver status of a Neon account. Return True if
    the account is bound by the waiver, False otherwise."""
    if now is None:
        now = datetime.datetime.now()

    if ack:  # Always overwrite existing signature data since re-acknowledged
        new_status = WAIVER_FMT.format(
            version=current_version, accepted=now.strftime("%Y-%m-%d")
        )
        print("Calling", set_waiver_status)
        set_waiver_status(user_id, new_status)
        print("Called set_waiver_status")
        return True

    # Precondition: ack = false
    # Check if signature on file, version is current, and not expired
    last_version = None
    last_signed = None
    if waiver_status is not None:
        match = re.match(WAIVER_REGEX, waiver_status)
        if match is not None:
            print(match)
            last_version = match[1]
            last_signed = dateparser.parse(match[2])
    if last_version is None:
        return False
    if last_version != current_version:
        return False
    expiry = last_signed + datetime.timedelta(days=expiration_days)
    return now < expiry
