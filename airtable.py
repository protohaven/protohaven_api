from http.client import HTTPSConnection
import httplib2
import json
import datetime
import urllib
import requests

#https://protohaven.app.neoncrm.com/np/admin/systemsetting/customDataEdit.do?id=75
from config import get_config
cfg = get_config()['airtable']
AIRTABLE_URL = f"https://api.airtable.com/v0/{cfg['base_id']}"
AIRTABLE_TOKEN = cfg['token']

class Tables:
	TOOLS = cfg['tables']['tools']
	CLEARANCES = cfg['tables']['clearances']

def get_all_records(tbl):
  url = f"{AIRTABLE_URL}/{tbl}"
  headers = {
    'Authorization': f'Bearer {AIRTABLE_TOKEN}',
    'Content-Type': 'application/json'
  }

  records = []
  offs = ""
  while offs is not None:
    response = requests.request("GET", f"{AIRTABLE_URL}/{tbl}?offset={offs}", headers=headers)
    if response.status_code != 200:
      raise Exception("Airtable fetch", response.status_code, response.content)
    data = json.loads(response.content)
    records += data['records']
    if data.get('offset') is None:
      return records
    offs = data['offset']

def insert_records(data, tbl):
  url = f"{AIRTABLE_URL}/{tbl}"
  headers = {
    'Authorization': f'Bearer {AIRTABLE_TOKEN}',
    'Content-Type': 'application/json'
  }
  post_data = dict(records=[
      dict(fields=d) for d in data
  ])
  response = requests.request("POST", url, headers=headers, data=json.dumps(post_data))
  return response


if __name__ == "__main__":
  print(get_all_records(Tables.CLEARANCES))
