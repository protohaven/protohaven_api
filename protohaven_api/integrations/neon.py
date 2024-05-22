""" Neon CRM integration methods """  # pylint: disable=too-many-lines
import datetime
import json
import logging
import re
import time
import urllib
from dataclasses import dataclass
from functools import cache

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from protohaven_api.config import get_config, tz, tznow
from protohaven_api.integrations.data.connector import get as get_connector
from protohaven_api.rbac import Role

log = logging.getLogger("integrations.neon")


def cfg(param):
    """Load neon configuration"""
    return get_config()["neon"][param]


TEST_MEMBER = 1727
GROUP_ID_CLEARANCES = 1


@dataclass
class CustomField:
    """Account Custom Fields from Neon"""

    API_SERVER_ROLE = 85
    CLEARANCES = 75
    INTEREST = 148
    EXPERTISE = 155
    DISCORD_USER = 150
    WAIVER_ACCEPTED = 151
    SHOP_TECH_SHIFT = 152
    SHOP_TECH_LAST_DAY = 158
    AREA_LEAD = 153
    ANNOUNCEMENTS_ACKNOWLEDGED = 154


@dataclass
class Category:
    """Event categories from Neon"""

    VOLUNTEER_DAY = "32"
    MEMBER_EVENT = "33"
    PROJECT_BASED_WORKSHOP = "15"
    SHOP_TECH = "34"
    SKILLS_AND_SAFETY_WORKSHOP = "16"
    SOMETHING_ELSE_AMAZING = "27"


WAIVER_FMT = "version {version} on {accepted}"
WAIVER_REGEX = r"version (.+?) on (.*)"
URL_BASE = "https://api.neoncrm.com/v2"
ADMIN_URL = "https://protohaven.app.neoncrm.com/np/admin"


def fetch_published_upcoming_events(back_days=7):
    """Load upcoming events from Neon CRM, with `back_days` of trailing event data.
    Note that querying is done based on the end date so multi-week intensives
    can still appear even if they started earlier than `back_days`."""
    q_params = {
        "endDateAfter": (tznow() - datetime.timedelta(days=back_days)).strftime(
            "%Y-%m-%d"
        ),
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
        content = get_connector().neon_request(
            cfg("api_key1"),
            "https://api.neoncrm.com/v2/events?" + encoded_params,
            "GET",
        )
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
    content = get_connector().neon_request(
        cfg("api_key1"), "https://api.neoncrm.com/v2/events?" + encoded_params, "GET"
    )
    if isinstance(content, list):
        raise RuntimeError(content)
    return content["events"]


def fetch_event(event_id):
    """Fetch data on an individual (legacy) event in Neon"""
    return get_connector().neon_request(
        cfg("api_key1"), f"https://api.neoncrm.com/v2/events/{event_id}"
    )


def fetch_registrations(event_id):
    """Fetch registrations for a specific Neon event"""
    content = get_connector().neon_request(
        cfg("api_key1"),
        f"https://api.neoncrm.com/v2/events/{event_id}/eventRegistrations",
    )
    if isinstance(content, list):
        raise RuntimeError(content)
    if content["pagination"]["totalPages"] > 1:
        raise RuntimeError("TODO implement pagination for fetch_attendees()")
    return content["eventRegistrations"] or []


def fetch_tickets(event_id):
    """Fetch ticket information for a specific Neon event"""
    content = get_connector().neon_request(
        cfg("api_key1"), f"https://api.neoncrm.com/v2/events/{event_id}/tickets"
    )
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
        content = get_connector().neon_request(
            cfg("api_key1"),
            url,
            "GET",
        )
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
    content = get_connector().neon_request(
        cfg("api_key1"), f"{URL_BASE}/customFields/{CustomField.CLEARANCES}", "GET"
    )
    return content["optionValues"]


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
        "id": CustomField.CLEARANCES,
        "displayType": "Checkbox",
        "name": "Clearances",
        "dataType": "Integer",
        "component": "Account",
        "optionValues": codes,
    }
    return get_connector().neon_request(
        cfg("api_key1"),
        f"{URL_BASE}/customFields/{CustomField.CLEARANCES}",
        "PUT",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )


def set_custom_field(user_id, data):
    """Set any custom field for a user in Neon"""
    data = {
        "individualAccount": {
            "accountCustomFields": [data],
        }
    }
    return get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/{user_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )


def set_interest(user_id, interest: str):
    """Assign interest to user custom field"""
    return set_custom_field(user_id, {"id": CustomField.INTEREST, "value": interest})


def set_discord_user(user_id, discord_user: str):
    """Sets the discord user used by this user"""
    return set_custom_field(
        user_id, {"id": CustomField.DISCORD_USER, "value": discord_user}
    )


def set_clearances(user_id, codes):
    """Sets all clearances for a specific user - company or individual"""
    code_to_id = {c["code"]: c["id"] for c in fetch_clearance_codes()}
    ids = [code_to_id[c] for c in codes if c in code_to_id.keys()]

    # Need to confirm whether the user is an individual or company account
    m = fetch_account(user_id)
    if m is None:
        return None

    data = {
        "accountCustomFields": [
            {"id": CustomField.CLEARANCES, "optionValues": [{"id": i} for i in ids]}
        ],
    }

    if m.get("individualAccount"):
        data = {"individualAccount": data}
    elif m.get("companyAccount"):
        data = {"companyAccount": data}
    else:
        raise RuntimeError("Unknown account type for " + str(user_id))

    return get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/{user_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )


def fetch_account(account_id):
    """Fetches account information for a specific user in Neon.
    Raises RuntimeError if an error is returned from the server"""
    content = get_connector().neon_request(
        cfg("api_key1"), f"https://api.neoncrm.com/v2/accounts/{account_id}"
    )
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
    content = get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/search",
        "POST",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    if content.get("searchResults") is None:
        raise RuntimeError(f"Search for {firstname} {lastname} failed: {content}")
    return content["searchResults"][0] if len(content["searchResults"]) > 0 else None

def _paginated_account_search(data):
  cur = 0
  data["pagination"] = {
      "currentPage": cur,
      "pageSize": 50,
  }
  total = 1
  while cur < total:
      content = get_connector().neon_request(
          cfg("api_key2"),
          f"{URL_BASE}/accounts/search",
          "POST",
          body=json.dumps(data),
          headers={"content-type": "application/json"},
      )
      if content.get("searchResults") is None or content.get("pagination") is None:
          raise RuntimeError(f"Search failed: {content}")

      total = content["pagination"]["totalPages"]
      cur += 1
      data["pagination"]["currentPage"] = cur
      for r in content["searchResults"]:
          yield r


def search_member(email, operator="EQUAL"):
    """Lookup a user by their email; note that emails aren't unique so we may
    return multiple results."""
    data = {
        "searchFields": [
            {
                "field": "Email",
                "operator": operator,
                "value": email,
            }
        ],
        "outputFields": [
            "Account ID",
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
        ],
    }
    return _paginated_account_search(data)


def get_members_with_role(role, extra_fields):
    """Fetch all members with a specific assigned role (e.g. all shop techs)"""
    data = {
        "searchFields": [
            {
                "field": str(CustomField.API_SERVER_ROLE),
                "operator": "CONTAIN",
                "value": role["id"],
            }
        ],
        "outputFields": ["Account ID", "First Name", "Last Name", *extra_fields],
    }
    return _paginated_account_search(data)

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
            CustomField.SHOP_TECH_LAST_DAY,
        ],
    ):
        clr = []
        if t.get("Clearances") is not None:
            clr = t["Clearances"].split("|")
        interest = t.get("Interest", "")
        expertise = t.get("Expertise", "")
        area_lead = t.get("Area Lead", "")
        shift = t.get("Shop Tech Shift", "")
        last_day = t.get("Shop Tech Last Day", "")
        techs.append(
            {
                "id": t["Account ID"],
                "name": f"{t['First Name']} {t['Last Name']}",
                "email": t["Email 1"],
                "interest": interest,
                "expertise": expertise,
                "area_lead": area_lead,
                "shift": shift,
                "last_day": last_day,
                "clearances": clr,
            }
        )
    techs.sort(key=lambda t: len(t["clearances"]))
    return techs


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

    def set_thumbnail(self, event_id, thumbnail_path):
        """Sets the thumbnail image for a neon event"""
        r = self.s.get(f"{ADMIN_URL}/event/eventDetails.do?id={event_id}")
        content = r.content.decode("utf8")
        if "Upload Thumbnail" not in content:
            log.debug(content)
            raise RuntimeError("BAD get event page")

        referer = (
            f"{ADMIN_URL}/event/uploadPhoto.do?eventId={event_id}&staffUpload=true"
        )
        ag = self.s.get(referer)
        content = ag.content.decode("utf8")
        if "Event Photo" not in content:
            raise RuntimeError("BAD get event photo upload page")

        self.s.headers.update({"Referer": ag.url})
        drt_i = self.drt.get()
        with open(thumbnail_path, "rb") as fh:
            multipart_form_data = {
                "z2DuplicateRequestToken": (None, drt_i),
                "eventImageForm": (thumbnail_path, fh),
            }
            rep = self.s.post(
                f"{ADMIN_URL}/event/photoSave.do",
                files=multipart_form_data,
                allow_redirects=False,
            )
        log.debug(rep.request.headers)
        log.debug(rep.request.body)
        log.debug("=========Response:========")
        log.debug(rep.status_code)
        log.debug(rep.content.decode("utf8"))
        return rep


def set_event_scheduled_state(neon_id, scheduled=True):
    """Publishes or unpublishes an event in Neon"""
    data = {
        "publishEvent": scheduled,
        "enableEventRegistrationForm": scheduled,
        "archived": not scheduled,
        "enableWaitListing": scheduled,
    }
    content = get_connector().neon_request(
        cfg("api_key3"),
        f"{URL_BASE}/events/{neon_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )
    return content["id"]


def create_event(  # pylint: disable=too-many-arguments
    name,
    desc,
    start,
    end,
    category=Category.PROJECT_BASED_WORKSHOP,
    max_attendees=6,
    dry_run=True,
):
    """Creates a new event in Neon CRM"""
    event = {
        "name": name,
        "summary": name,
        "maximumAttendees": max_attendees,
        "category": {"id": category},
        "publishEvent": True,
        "enableEventRegistrationForm": True,
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
        # "financialSettings": {
        #  "feeType": "SingleFee",
        #  "admissionFee": {
        #    "fee": price,
        #  },
        # },
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
        cfg("api_key3"),
        f"{URL_BASE}/events",
        "POST",
        body=json.dumps(event),
        headers={"content-type": "application/json"},
    )
    return evt_request["id"]


def create_coupon_code(code, amt):
    """Creates a coupon code for a specific absolute amount"""
    n = NeonOne(cfg("login_user"), cfg("login_pass"))
    return n.create_single_use_abs_event_discount(code, amt)


def soft_search(keyword):
    """Creates a coupon code for a specific absolute amount"""
    n = NeonOne(cfg("login_user"), cfg("login_pass"))
    return n.soft_search(keyword)


def _patch_role(account, role, enabled):
    acf = account.get("individualAccount", account.get("companyAccount"))[
        "accountCustomFields"
    ]
    for cf in acf:
        if str(cf["id"]) == str(CustomField.API_SERVER_ROLE):
            vals = {v["id"]: v["name"] for v in cf["optionValues"]}
            if enabled:
                vals[role["id"]] = role["name"]
            else:
                del vals[role["id"]]
            return [{"id": k, "name": v} for k, v in vals.items()]
    return [role] if enabled else []


def patch_member_role(email, role, enabled):
    """Enables or disables a specific role for a user with the given `email`"""
    mem = search_member(email)
    if len(mem) == 0:
        raise KeyError()
    user_id = mem[0]["Account ID"]
    log.debug("patching account")
    account = fetch_account(mem[0]["Account ID"])
    roles = _patch_role(account, role, enabled)
    log.debug(str(roles))
    data = {
        "accountCustomFields": [
            {"id": CustomField.API_SERVER_ROLE, "optionValues": roles}
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
    return get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/{user_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )


def set_tech_custom_fields(  # pylint: disable=too-many-arguments
    user_id, shift=None, last_day=None, area_lead=None, interest=None, expertise=None
):
    """Overwrites existing waiver status information on an account"""
    cf = []
    if shift is not None:
        cf.append({"id": CustomField.SHOP_TECH_SHIFT, "value": shift})
    if last_day is not None:
        cf.append({"id": CustomField.SHOP_TECH_LAST_DAY, "value": last_day})
    if area_lead is not None:
        cf.append({"id": CustomField.AREA_LEAD, "value": area_lead})
    if interest is not None:
        cf.append({"id": CustomField.INTEREST, "value": interest})
    if expertise is not None:
        cf.append({"id": CustomField.EXPERTISE, "value": interest})
    data = {"accountCustomFields": cf}
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
    return get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/{user_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )


def _set_custom_singleton_fields(user_id, field_id_to_value_map):
    data = {
        "accountCustomFields": [
            {"id": k, "value": v} for k, v in field_id_to_value_map.items()
        ],
    }
    # Need to confirm whether the user is an individual or company account
    m = fetch_account(user_id)
    if m is None:
        raise RuntimeError(
            f"Failed to resolve account type for setting fields: {field_id_to_value_map}"
        )

    if m.get("individualAccount"):
        data = {"individualAccount": data}
    elif m.get("companyAccount"):
        data = {"companyAccount": data}
    else:
        raise RuntimeError("Unknown account type for " + str(user_id))

    return get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/{user_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )


def set_waiver_status(user_id, new_status):
    """Overwrites existing waiver status information on an account"""
    data = {
        "accountCustomFields": [
            {"id": CustomField.WAIVER_ACCEPTED, "value": new_status}
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

    return get_connector().neon_request(
        cfg("api_key2"),
        f"{URL_BASE}/accounts/{user_id}",
        "PATCH",
        body=json.dumps(data),
        headers={"content-type": "application/json"},
    )


def update_announcement_status(user_id, now=None):
    """Updates announcement acknowledgement"""
    if now is None:
        now = tznow()
    return _set_custom_singleton_fields(
        user_id, {CustomField.ANNOUNCEMENTS_ACKNOWLEDGED: now.strftime("%Y-%m-%d")}
    )


def update_waiver_status(  # pylint: disable=too-many-arguments
    user_id,
    waiver_status,
    ack,
    now=None,
    current_version=None,
    expiration_days=None,
):
    """Update the liability waiver status of a Neon account. Return True if
    the account is bound by the waiver, False otherwise."""

    # Lazy load config entries to prevent parsing errors on init
    if now is None:
        now = tznow()
    if current_version is None:
        current_version = cfg("waiver_published_date")
    if expiration_days is None:
        expiration_days = cfg("waiver_expiration_days")

    if ack:  # Always overwrite existing signature data since re-acknowledged
        new_status = WAIVER_FMT.format(
            version=current_version, accepted=now.strftime("%Y-%m-%d")
        )
        log.debug(f"Calling {set_waiver_status}")
        set_waiver_status(user_id, new_status)
        log.debug("Called set_waiver_status")
        return True

    # Precondition: ack = false
    # Check if signature on file, version is current, and not expired
    last_version = None
    last_signed = None
    if waiver_status is not None:
        match = re.match(WAIVER_REGEX, waiver_status)
        if match is not None:
            log.debug(str(match))
            last_version = match[1]
            last_signed = dateparser.parse(match[2]).astimezone(tz)
    if last_version is None:
        return False
    if last_version != current_version:
        return False
    expiry = last_signed + datetime.timedelta(days=expiration_days)
    return now < expiry


def income_condition(income_name, income_value):
    """Generates an "income condition" for making specific pricing of tickets available"""
    return [
        [
            {
                "name": "account_custom_view.field78",
                "displayName": "Income Based Rates",
                "groupId": "220",
                "savedGroup": "1",
                "operator": "1",
                "operatorName": "Equal",
                "optionName": income_name,
                "optionValue": str(income_value),
            }
        ]
    ]


def membership_condition(mem_names, mem_values):
    """Generates a "membership condition" for making specific ticket prices available"""
    stvals = [f"'{v}'" for v in mem_values]
    stvals = f"({','.join(stvals)})"
    return [
        [
            {
                "name": "membership_listing.membershipId",
                "displayName": "Membership+Level",
                "groupId": "55",
                "savedGroup": "1",
                "operator": "9",
                "operatorName": "In Range Of",
                "optionName": " or ".join(mem_names),
                "optionValue": stvals,
            }
        ]
    ]


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
        "cond": income_condition("Extremely Low Income - 70%", 43),
        "price_ratio": 0.3,
        "qty_ratio": 0.25,
        "price_name": "AMP Rate",
    },
    {
        "name": "VLI - Price",
        "desc": "50% Of",
        "cond": income_condition("Very Low Income - 50%", 42),
        "price_ratio": 0.5,
        "qty_ratio": 0.25,
        "price_name": "AMP Rate",
    },
    {
        "name": "LI - Price",
        "desc": "20% Of",
        "cond": income_condition("Low Income - 20%", 41),
        "price_ratio": 0.8,
        "qty_ratio": 0.5,
        "price_name": "AMP Rate",
    },
    {
        "name": "Member Discount",
        "desc": "20% Of",
        "cond": membership_condition(
            [
                "General+Membership",
                "Primary+Family+Membership",
                "Additional+Family+Membership",
            ],
            [1, 27, 26],
        ),
        "price_ratio": 0.8,
        "qty_ratio": 1.0,
        "price_name": "Member Rate",
    },
    {
        "name": "Instructor Discount",
        "desc": "50% Of",
        "cond": membership_condition(["Instructor"], [9]),
        "price_ratio": 0.5,
        "qty_ratio": 1.0,
        "price_name": "Instructor Rate",
    },
]


def assign_pricing(event_id, price, seats, clear_existing=False, n=None):
    """Assigns ticket pricing and quantities for a preexisting Neon event"""
    if n is None:
        n = NeonOne(cfg("login_user"), cfg("login_pass"))

    if clear_existing:
        n.delete_all_prices_and_groups(event_id)

    for p in pricing:
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
