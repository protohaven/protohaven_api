from http.client import HTTPSConnection
from functools import cache
import httplib2
import json
import datetime
import urllib
import requests

#https://protohaven.app.neoncrm.com/np/admin/systemsetting/customDataEdit.do?id=75
from config import get_config
cfg = get_config()['airtable']
AIRTABLE_URL = f"https://api.airtable.com/v0"

def get_record(base, tbl, rec):
  url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}/{rec}"
  headers = {
    'Authorization': f"Bearer {cfg[base]['token']}",
    'Content-Type': 'application/json'
  }
  response = requests.request("GET", url, headers=headers)
  if response.status_code != 200:
    raise Exception("Airtable fetch", response.status_code, response.content)
  return json.loads(response.content)

def get_all_records(base, tbl):
  url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}"
  headers = {
    'Authorization': f"Bearer {cfg[base]['token']}",
    'Content-Type': 'application/json'
  }
  records = []
  offs = ""
  while offs is not None:
    url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}?offset={offs}"
    response = requests.request("GET", url, headers=headers)
    if response.status_code != 200:
      raise Exception("Airtable fetch", response.status_code, response.content)
    data = json.loads(response.content)
    records += data['records']
    if data.get('offset') is None:
      return records
    offs = data['offset']

def insert_records(data, base, tbl):
  url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}"
  headers = {
    'Authorization': f"Bearer {cfg[base]['token']}",
    'Content-Type': 'application/json'
  }
  post_data = dict(records=[
      dict(fields=d) for d in data
  ])
  response = requests.request("POST", url, headers=headers, data=json.dumps(post_data))
  return response


def update_record(data, base, tbl, rec):
  url = f"{AIRTABLE_URL}/{cfg[base]['base_id']}/{cfg[base][tbl]}/{rec}"
  headers = {
    'Authorization': f"Bearer {cfg[base]['token']}",
    'Content-Type': 'application/json'
  }
  post_data = dict(fields=data)
  response = requests.request("PATCH", url, headers=headers, data=json.dumps(post_data))
  return response

def get_class_automation_schedule():
    return get_all_records('class_automation', 'schedule')

@cache
def get_instructor_log_tool_codes():
    codes = get_all_records('class_automation', 'clearance_codes')
    individual = tuple(c['fields']['Form Name'] for c in codes if c['fields'].get('Individual'))
    return individual

def respond_class_automation_schedule(eid, pub):
    if pub:
      data = dict(Confirmed=datetime.datetime.now().isoformat())
    else:
      data = dict(Confirmed="")
    return update_record(data, 'class_automation', 'schedule', eid)

def mark_schedule_supply_request(eid, missing):
    return update_record({'Supply State': 'Supplies Requested' if missing else 'Supplies Confirmed'}, 'class_automation', 'schedule', eid)

def get_tools():
    return get_all_records('tools_and_equipment', 'tools')


if __name__ == "__main__":
  print(get_all_records(Tables.CLEARANCES))
