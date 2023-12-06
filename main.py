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
app.config['TEMPLATES_AUTO_RELOAD'] = True # Reload template if signature differs

import neon
import airtable
import datetime
import time
import json
import oauth

def require_login(fn):
    def do_login_check(*args, **kwargs):
        if session.get('neon_id') is None:
            session['redirect_to_login_url'] = request.url
            return redirect(url_for(login_user_neon_oauth.__name__))
        return fn(*args, **kwargs)
    do_login_check.__name__ = fn.__name__
    return do_login_check 

def user_email():
    acct = session.get('neon_account')['individualAccount']
    return acct['primaryContact']['email1']

def user_fullname():
    acct = session.get('neon_account')['individualAccount']
    return acct['primaryContact']['firstName'] + ' ' + acct['primaryContact']['lastName']

@app.route("/")
@require_login
def index():
    neon_account = session.get('neon_account')
    neon_account['custom_fields'] = {}
    neon_json = json.dumps(neon_account, indent=2)
    for cf in neon_account['individualAccount']['accountCustomFields']:
        neon_account['custom_fields'][cf['name']] = cf
    return render_template("dashboard.html", fullname=user_fullname(), email=user_email(), neon_id=session.get('neon_id'), neon_account=neon_account, neon_json=neon_json)

@app.route("/login")
def login_user_neon_oauth():
    referrer = request.referrer
    if referrer is None:
        referrer = session.get('redirect_to_login_url')
    if referrer is None or referrer == "/login":
        referrer = "/"
    session['login_referrer'] = referrer 
    
    print("Set login referrer:", session['login_referrer'])
    return redirect(oauth.prep_request(
        "https://api.protohaven.org/oauth_redirect"))
       # request.url_root + url_for(neon_oauth_redirect.__name__)))

@app.route("/logout")
def logout():
    session['neon_id'] = None
    session['neon_account'] = None
    return "You've been logged out"

@app.route("/oauth_redirect")
def neon_oauth_redirect():
    code = request.args.get('code')
    rep = oauth.retrieve_token(url_for(neon_oauth_redirect.__name__), code)
    session['neon_id'] = rep.get("access_token")
    session['neon_account'] = neon.fetch_account(session['neon_id'])
    referrer = session.get('login_referrer', '/')
    print("Login referrer redirect:", referrer)
    return redirect(referrer)

@app.route("/instructor/events")
@require_login
def instructor_events():
    after_date = datetime.datetime.now() - datetime.timedelta(hours=24)
    email = user_email()
    sched = [(s, neon.fetch_attendees(s['id'])) for s in neon.fetch_events(after=after_date)]
    return render_template("instructor_events.html", schedule=sched)

@app.route("/instructor/class_selector")
@require_login
def instructor_class_selector():
    email = user_email()
    sched = [(s['id'], s['fields']) for s in airtable.get_class_automation_schedule() if s['fields']['Email'] == email]
    return render_template("instructor_class_selector.html", schedule=sched)

@app.route("/instructor/class_selector/update", methods=["POST"])
@require_login
def instructor_class_selector_update():
    email = user_email()
    eid = request.form.get('eid')
    pub = request.form.get('pub') == 'true'
    return airtable.respond_class_automation_schedule(eid, pub).content


# TODO cache events, attendees, and emails
@app.route("/instructor_hours")
@require_login
def instructor_hours_handler():
  events = neon.fetch_events(datetime.datetime.now() - datetime.timedelta(days=14))
  print("Fetched", len(events), "events")

  def prefill(instructor, start_date, hours, class_name, pass_emails, clearances):
      start_yyyy_mm_dd = start_date.strftime('%Y-%m-%d')
      return f"https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform?usp=pp_url&entry.1719418402={instructor}&entry.1405633595={start_yyyy_mm_dd}&entry.1276102155={hours}&entry.654625226={class_name}&entry.362496408=Nope,+just+a+single+session+class&entry.204701066={pass_emails}&entry.965251553={clearances}&entry.1116111507=No"
  result = []
  for e in events:
      e['attendees'] = []
      if user_fullname() not in e['name']:
          print("Skipping", e['name'], "not taught by logged in user")
          continue
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
        instructor=user_fullname(),
        start_date=datetime.datetime.strptime(e['startDate'], '%Y-%m-%d'),
        hours=3, # TODO fetch from class
        class_name=e['name'],
        pass_emails=", ".join(e['attendees']), # TODO Fetch event registrations
        clearances='', # TODO extract clearance details from a new event custom field
        )
      result.append(e)

  return render_template("instructor_hours.html", events=result)

if __name__ == "__main__":
  app.run()
