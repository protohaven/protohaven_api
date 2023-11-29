#!/usr/bin/env python
from http.client import HTTPSConnection
import httplib2
import json
import datetime
import urllib
import yaml

CONFIG_PATH = "config.yaml"
def get_config():
	with open(CONFIG_PATH, "r") as f:
		return yaml.load(f.read())

def fetch_neon_events():
  # Load events from Neon CRM
  cfg = get_config()

  q_params = {'startDateAfter': (datetime.datetime.now() - datetime.timedelta(days=14)).strftime('%Y-%m-%d'),
              'publishedEvent': True}
  encoded_params = urllib.parse.urlencode(q_params)
  h = httplib2.Http(".cache")
  h.add_credentials(cfg.neon_events.username, cfg.neon_events.password) # Basic authentication
  resp, content = h.request("https://api.neoncrm.com/v2/events?" + encoded_params, "GET")

  neon_events = json.loads(content)['events']
  return neon_events

#for evt in fetch_neon_events():
#  print(json.dumps(evt) + "\n")
