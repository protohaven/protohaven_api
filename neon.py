#!/usr/bin/env python
from http.client import HTTPSConnection
import httplib2
import json
import datetime
import time
import urllib
import yaml
import requests
from bs4 import BeautifulSoup

from config import get_config
cfg = get_config()['neon']
TEST_MEMBER = 1727
GROUP_ID_CLEARANCES = 1
CUSTOM_FIELD_CLEARANCES = 75
CUSTOM_FIELD_INTEREST = 148
CUSTOM_FIELD_DISCORD_USER = 150
URL_BASE = "https://api.neoncrm.com/v2"

def fetch_events(after=None, before=None, published=True):
  # Load events from Neon CRM
  q_params = {'publishedEvent': published}
  if after is not None:
    q_params['startDateAfter'] = after.strftime('%Y-%m-%d')
  if before is not None:
    q_params['startDateBefore'] = before.strftime('%Y-%m-%d')

  encoded_params = urllib.parse.urlencode(q_params)
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key1'])
  resp, content = h.request("https://api.neoncrm.com/v2/events?" + encoded_params, "GET")
  content = json.loads(content)
  if type(content) is list:
      raise Exception(content)
  return content['events'] 

def fetch_event(event_id):
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key1'])
  resp, content = h.request(f"https://api.neoncrm.com/v2/events/{event_id}")
  if resp.status != 200:
      raise Exception(f"fetch_event({event_id}) {resp.status}: {content}")
  return json.loads(content)

def fetch_attendees(event_id):
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key1'])
  resp, content = h.request(f"https://api.neoncrm.com/v2/events/{event_id}/attendees")
  if resp.status != 200:
      raise Exception(f"fetch_attendees({event_id}) {resp.status}: {content}")
  content = json.loads(content)

  if type(content) is list:
      raise Exception(content)
  if content['pagination']['totalPages'] > 1:
      raise Exception("TODO implement pagination for fetch_attendees()")
  return content['attendees'] or []

def fetch_clearance_codes():
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key1'])
  resp, content = h.request(f"{URL_BASE}/customFields/{CUSTOM_FIELD_CLEARANCES}", "GET")
  assert(resp.status == 200)
  return json.loads(content)['optionValues']

def get_user_clearances(account_id):
    # TODO cache
    id_to_code = dict([(c['id'], c['code']) for c in fetch_clearance_codes()])
    acc = fetch_account(account_id)
    if acc is None:
        raise Exception("Account not found")
    custom = acc.get('individualAccount', acc.get('companyAccount'))['accountCustomFields'] 
    for cf in custom:
        if cf['name'] == 'Clearances':
            return [id_to_code.get(v['id']) for v in cf['optionValues']]
    return []

def set_clearance_codes(codes):
  #ids = [code_mapping[c]['id'] for c in codes]
  data = {
    "groupId": GROUP_ID_CLEARANCES,
    "id": CUSTOM_FIELD_CLEARANCES,
    "displayType": "Checkbox",
    "name": "Clearances",
    "dataType": "Integer",
    "component": "Account",
    "optionValues": codes,
  }
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key1'])
  resp, content = h.request(
      f"{URL_BASE}/customFields/{CUSTOM_FIELD_CLEARANCES}", "PUT",
      body=json.dumps(data), headers={'content-type':'application/json'})
  print("PUT", resp.status, content)


def set_custom_field(user_id, data):
  data = {
    "individualAccount": {
      "accountCustomFields": [data],
    }
  }
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key2'])
  resp, content = h.request(
      f"{URL_BASE}/accounts/{user_id}", "PATCH",
      body=json.dumps(data), headers={'content-type':'application/json'})
  print("PATCH", resp.status, content)

def set_interest(user_id, interest:str):
    return set_custom_field(user_id, dict(id=CUSTOM_FIELD_INTEREST, value=interest))

def set_discord_user(user_id, discord_user:str):
    return set_custom_field(user_id, dict(id=CUSTOM_FIELD_DISCORD_USER, value=discord_user))

def set_clearances(user_id, codes):
  code_to_id = dict([(c['code'], c['id']) for c in fetch_clearance_codes()])
  ids = [code_to_id[c] for c in codes]
  data = {
    "individualAccount": {
      "accountCustomFields": [
        {
          "id": CUSTOM_FIELD_CLEARANCES,
          "optionValues": [{"id": i} for i in ids]
        }
      ],
    }
  }
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key2'])
  resp, content = h.request(
      f"{URL_BASE}/accounts/{user_id}", "PATCH",
      body=json.dumps(data), headers={'content-type':'application/json'})
  print("PATCH", resp.status, content)
  return resp, content


def fetch_account(account_id):
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key1'])
  resp, content = h.request(f"https://api.neoncrm.com/v2/accounts/{account_id}")
  content = json.loads(content)
  if type(content) is list:
      raise Exception(content)
  return content

def search_member_by_name(firstname, lastname):
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
      }
    ],
    "outputFields": [
      "Account ID",
      "Email 1",
    ],
    "pagination": {
      "currentPage": 0,
      "pageSize": 1,
    }
  }
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key2'])
  resp, content = h.request(
      f"{URL_BASE}/accounts/search",
      "POST", body=json.dumps(data), headers={'content-type':'application/json'})
  if resp.status != 200:
    raise Exception(f"Error {resp.status}: {content}")
  content = json.loads(content)
  if content.get('searchResults') is None:
    raise Exception(f"Search for {email} failed: {content}")
  return content['searchResults'][0] if  len(content['searchResults']) > 0 else None

def search_member(email):
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
    ],
    "pagination": {
      "currentPage": 0,
      "pageSize": 1,
    }
  }
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key2'])
  resp, content = h.request(
      f"{URL_BASE}/accounts/search",
      "POST", body=json.dumps(data), headers={'content-type':'application/json'})
  if resp.status != 200:
    raise Exception(f"Error {resp.status}: {content}")
  content = json.loads(content)
  if content.get('searchResults') is None:
    raise Exception(f"Search for {email} failed: {content}")
  return content['searchResults'][0] if  len(content['searchResults']) > 0 else None

def getMembersWithRole(role, extra_fields):
  # Do we need to search email 2 and 3 as well?
  cur = 0
  data = {
    "searchFields": [{
        "field": "85",
        "operator": "CONTAIN",
        "value": role['id'],   
    }],
    "outputFields": [
      "Account ID",
      "First Name", 
      "Last Name",
      *extra_fields
    ],
    "pagination": {
      "currentPage": cur,
      "pageSize": 50,
    }
  }
  total = 1
  result = []
  h = httplib2.Http(".cache")
  h.add_credentials(cfg['domain'], cfg['api_key2'])
  while cur < total:
    resp, content = h.request(
        f"{URL_BASE}/accounts/search",
        "POST", body=json.dumps(data), headers={'content-type':'application/json'})
    if resp.status != 200:
      raise Exception(f"Error {resp.status}: {content}")
    content = json.loads(content)
    if content.get('searchResults') is None or content.get('pagination') is None:
      raise Exception(f"Search for {email} failed: {content}")

    #print(f"======= Page {cur} of {total} (size {len(content['searchResults'])}) =======")
    total = content['pagination']['totalPages']
    cur += 1
    data['pagination']['currentPage'] = cur

    for r in content['searchResults']:
      yield r

class DuplicateRequestToken:
  def __init__(self):
    self.i = int(time.time())
  def get(self):
    self.i += 1
    return self.i

class NeonOne:
  TYPE_MEMBERSHIP_DISCOUNT = 2
  TYPE_EVENT_DISCOUNT = 3

  def __init__(self, user, passwd):
    self.s = requests.Session()
    self.drt = DuplicateRequestToken()
    self._do_login(user, passwd)

  def _do_login(self, user, passwd):
    csrf = self._get_csrf()
    print("CSRF:", csrf)

    # Submit login info to initial login page
    r = self.s.post("https://app.neonsso.com/login",
                    data=dict(_token=csrf, email=user, password=passwd))
    assert r.status_code == 200

    # Select Neon SSO and go through the series of SSO redirects to properly set cookies
    r = self.s.get("https://app.neoncrm.com/np/ssoAuth")
    dec = r.content.decode("utf8")
    if "Mission Control Dashboard" not in dec:
        raise Exception(dec)

  def _get_csrf(self):
    rlogin = self.s.get("https://app.neonsso.com/login")
    assert rlogin.status_code == 200
    csrf = None
    soup = BeautifulSoup(rlogin.content.decode("utf8"), features="html.parser")
    for m in soup.head.find_all("meta"):
      if m.get('name') == "csrf-token":
        csrf = m['content']
    return csrf

  def create_single_use_abs_event_discount(self, code, amt):
    return self._post_discount(self.TYPE_EVENT_DISCOUNT, code=code, pct=False, amt=amt)

  def _post_discount(self, typ, code, pct, amt, from_date='11/19/2023', to_date='11/21/2024', max_uses=1):
    # We must appear to be coming from the specific discount settings page (Event or Membership)
    referer = f"https://protohaven.app.neoncrm.com/np/admin/systemsetting/newCouponCodeDiscount.do?sellingItemType={typ}&discountType=1"
    rg = self.s.get(referer)
    assert rg.status_code == 200

    # Must set referer so the server knows which "selling item type" this POST is for
    self.s.headers.update(dict(Referer=rg.url))
    drt_i = self.drt.get()
    data = {
        'z2DuplicateRequestToken': drt_i,
        'priceOff': 'coupon',
        'currentDiscount.couponCode': code,
        'currentDiscount.sellingItemId': '',
        'currentDiscount.maxUses': max_uses,
        'currentDiscount.validFromDate': from_date,
        'currentDiscount.validToDate': to_date,
        'currentDiscount.percentageValue': 1 if pct else 0,
        'submit': ' Save ',
    }
    if typ == self.TYPE_EVENT_DISCOUNT:
      data['currentDiscount.eventTicketPackageGroupId'] = ''

    if pct:
      data['currentDiscount.percentageDiscountAmount'] = amt
    else:
      data['currentDiscount.absoluteDiscountAmount'] = amt

    r = self.s.post(
        'https://protohaven.app.neoncrm.com/np/admin/systemsetting/couponCodeDiscountSave.do',
        allow_redirects=False, data =data)

    #print(r)
    #print("Request")
    #print(r.request.url)
    #print(r.request.body)
    #print(r.request.headers)

    print("Response")
    print(r.status_code)
    print(r.headers)

    if not "discountList.do" in r.headers.get('Location', ''):
        raise Exception("Failed to land on appropriate page - wanted discountList.do, got " + r.headers.get('Location', ''))
    return code


def create_coupon_code(code, amt):
    n = NeonOne(cfg['login_user'], cfg['login_pass'])
    return n.create_single_use_abs_event_discount(code, amt)
