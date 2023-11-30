#import os
#import sys

#sys.path.insert(0, os.path.dirname(__file__))

#def application(environ, start_response):
#    start_response('200 OK', [('Content-Type', 'text/plain')])
#    message = 'It works!\n'
#    version = 'Python v' + sys.version.split()[0] + '\n'
#    response = '\n'.join([message, version])
#    return [response.encode()]

from flask import Flask, render_template, session, redirect, request, url_for

from config import get_config

app = Flask(__name__)
application = app # our hosting requires application in passenger_wsgi
cfg = get_config()['general']
app.secret_key = cfg['session_secret']

import neon
import datetime
import time
import json
import oauth

def require_login(fn):
    def do_login_check(*args, **kwargs):
        if session.get('neon_id') is None:
            return redirect(url_for(login_user_neon_oauth.__name__))
        return fn(*args, **kwargs)
    do_login_check.__name__ = fn.__name__
    return do_login_check 

@app.route("/")
@require_login
def index():
    return f"This is Helloo World! User {session.get('neon_id')}\n"

@app.route("/login")
def login_user_neon_oauth():
    session['login_referrer'] = request.referrer or "/"
    return redirect(oauth.prep_request(
        "https://api.protohaven.org/oauth_redirect"))
       # request.url_root + url_for(neon_oauth_redirect.__name__)))

@app.route("/oauth_redirect")
def neon_oauth_redirect():
    code = request.args.get('code')
    rep = oauth.retrieve_token(url_for(neon_oauth_redirect.__name__), code)
    session['neon_id'] = rep.get("access_token")
    return redirect(session.get('login_referrer', '/')) 

# TODO cache events, attendees, and emails
@app.route("/instructor_hours")
@require_login
def instructor_hours_handler():
  events = neon.fetch_events(datetime.datetime.now() - datetime.timedelta(days=14))
  print("Fetched", len(events), "events")

  def prefill(instructor, start_date, hours, class_name, pass_emails, clearances):
      start_yyyy_mm_dd = start_date.strftime('%Y-%m-%d')
      return f"https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform?usp=pp_url&entry.1719418402={instructor}&entry.1405633595={start_yyyy_mm_dd}&entry.1276102155={hours}&entry.654625226={class_name}&entry.362496408=Nope,+just+a+single+session+class&entry.204701066={pass_emails}&entry.965251553={clearances}&entry.1116111507=No"
  for e in events:
      e['attendees'] = []
      for a in neon.fetch_attendees(e['id']):
          email = "please add email here"
          if a['accountId']:
              print("Fetch account for", a['accountId'])
              acc = neon.fetch_account(a['accountId'])
              if acc is not None:
                email = acc['individualAccount']['primaryContact']['email1'] 
          e['attendees'].append(f"{a['firstName']} {a['lastName']} ({email})")
          time.sleep(0.22) # API limits fetching to 5 per second

      print(f"Attendees for {e['name']}:", e['attendees'])
      e['prefill_form'] = prefill(
        instructor='', # TODO extract instructor from a new event custom field
        start_date=datetime.datetime.strptime(e['startDate'], '%Y-%m-%d'),
        hours=3, # TODO fetch from class
        class_name=e['name'],
        pass_emails=", ".join(e['attendees']), # TODO Fetch event registrations
        clearances='', # TODO extract clearance details from a new event custom field
        )

  return render_template("instructor_hours.html", events=events)

if __name__ == "__main__":
  app.run()
