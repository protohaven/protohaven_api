# Calendar fetching
# Requires access to be granted: https://calendar.google.com/calendar/u/0/embed?src=c_ab048e21805a0b5f7f094a81f6dbd19a3cba5565b408962565679cd48ffd02d9@group.calendar.google.com&ctz=America/New_York

from datetime import datetime, timedelta
from dateutil import parser
from collections import defaultdict
import os.path
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import get_config

cfg = get_config()['calendar']
CALENDAR_ID = cfg['id']

#If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
def fetch_instructor_schedules():
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists('token.json'):
      creds = Credentials.from_authorized_user_file('token.json', SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
      if creds and creds.expired and creds.refresh_token:
          creds.refresh(Request())
      else:
          flow = InstalledAppFlow.from_client_secrets_file(
              'credentials.json', SCOPES)
          creds = flow.run_local_server(port=0)
      # Save the credentials for the next run
      with open('token.json', 'w') as token:
          token.write(creds.to_json())

  service = build('calendar', 'v3', credentials=creds)
  # Call the Calendar API
  now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
  timeMax = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'  # 'Z' indicates UTC time
  events_result = service.events().list(calendarId=CALENDAR_ID,
                                        timeMin=now,
                                        timeMax=timeMax,
                                        maxResults=100,
                                        singleEvents=True,
                                        orderBy='startTime').execute()
  events = events_result.get('items', [])
  if not events:
      raise Exception('No upcoming events found.')
      return
  # Bin by event (aka instructor) name
  output = my_dict = defaultdict(list)
  for event in events:
      name = event["summary"]
      start = parser.parse(event['start'].get('dateTime', event['start'].get('date'))).isoformat()
      end = parser.parse(event['end'].get('dateTime', event['end'].get('date'))).isoformat()
      output[name].append([start, end])

  return output


def fetch_formatted_schedule():
  # Fetch schedule info from google calendar
  from collections import defaultdict
  import re
  sched = fetch_instructor_schedules()
  print(f"Found {len(sched)} instructor schedule events")
  print(sched)
  sched_formatted = defaultdict(list)
  for k,v in sched.items():
    # TODO remove once properly formatted
    k = k.split(" (", 1)[0]
    sched_formatted[k] += v
  print(sched_formatted)
  return sched_formatted

