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
import asyncio

from config import get_config

app = Flask(__name__)
application = app # our hosting requires application in passenger_wsgi
cfg = get_config()['general']
app.secret_key = cfg['session_secret']
app.config['TEMPLATES_AUTO_RELOAD'] = True # Reload template if signature differs

import neon
import airtable
import discord_bot
import wiki
import datetime
import time
import json
import oauth
from dateutil import parser as dateparser
import pytz

class Role:
    INSTRUCTOR = dict(name="Instructor", id="75")
    SHOP_TECH = dict(name="Shop Tech", id="238")
    SHOP_TECH_LEAD = dict(name="Shop Tech Lead", id="241")
    ONBOARDING = dict(name="Onboarding", id="240")
    ADMIN = dict(name="Admin", id="239")

def require_login(fn):
    def do_login_check(*args, **kwargs):
        if session.get('neon_id') is None:
            session['redirect_to_login_url'] = request.url
            return redirect(url_for(login_user_neon_oauth.__name__))
        return fn(*args, **kwargs)
    do_login_check.__name__ = fn.__name__
    return do_login_check 

def require_login_role(role):
    def fn_setup(fn):
        def do_role_check(*args, **kwargs):
            neon_acct = session.get('neon_account')
            if neon_acct is None:
                session['redirect_to_login_url'] = request.url
                return redirect(url_for(login_user_neon_oauth.__name__))
            
            acct = neon_acct.get('individualAccount') or neon_acct.get('companyAccount')
            if acct is None:
                session['redirect_to_login_url'] = request.url
                return redirect(url_for(login_user_neon_oauth.__name__))

            for cf in acct.get('accountCustomFields', []):
                if cf['name'] == 'API server role':
                    for ov in cf['optionValues']:
                        if role['name'] == ov.get('name'):
                            return fn(*args, **kwargs)
            return "Access Denied"
        do_role_check.__name__ = fn.__name__
        return do_role_check
    return fn_setup

def user_email():
    acct = session.get('neon_account')['individualAccount']
    return acct['primaryContact']['email1']

def user_fullname():
    acct = session.get('neon_account')['individualAccount']
    return acct['primaryContact']['firstName'] + ' ' + acct['primaryContact']['lastName']

def prefill_form(instructor, start_date, hours, class_name, pass_emails, clearances, volunteer, event_id):
    individual = airtable.get_instructor_log_tool_codes()
    clearance_codes = []
    tool_codes = []
    for c in clearances:
        if c in individual:
            tool_codes.append(c)
        else:
            clearance_codes.append(c)

    start_yyyy_mm_dd = start_date.strftime('%Y-%m-%d')
    result = "https://docs.google.com/forms/d/e/1FAIpQLScX3HbZJ1-Fm_XPufidvleu6iLWvMCASZ4rc8rPYcwu_G33gg/viewform?usp=pp_url"
    result += f"&entry.1719418402={instructor}"
    result += f"&entry.1405633595={start_yyyy_mm_dd}"
    result += f"&entry.1276102155={hours}"
    result += f"&entry.654625226={class_name}"
    if volunteer:
        result += f"&entry.1406934632=Yes,+please+donate+my+time."
    result += "&entry.362496408=Nope,+just+a+single+session+class"
    result += f"&entry.204701066={', '.join(pass_emails)}"
    for cc in clearance_codes:
        result += f"&entry.965251553={cc}"
    result += f"&entry.1116111507={'Yes' if len(tool_codes) > 0 else 'No'}"
    result += f"&entry.1646535924={event_id}"
    for tc in tool_codes:
        result += f"&entry.1725748243={tc}"
    print(result)
    return result


@app.route("/")
@require_login
def index():
    neon_account = session.get('neon_account')
    clearances = []
    roles = []
    neon_account['custom_fields'] = {'Clearances': {'optionValues': []}}
    neon_json = json.dumps(neon_account, indent=2)
    for cf in neon_account['individualAccount']['accountCustomFields']:
        if cf['name'] == 'Clearances':
            clearances = [v['name'] for v in cf['optionValues']]
        if cf['name'] == 'API server role':
            roles = [v['name'] for v in cf['optionValues']]
        neon_account['custom_fields'][cf['name']] = cf

    return render_template("dashboard.html", 
            fullname=user_fullname(), 
            email=user_email(), 
            neon_id=session.get('neon_id'), 
            neon_account=neon_account, 
            neon_json=neon_json, 
            clearances=clearances, 
            roles=roles)

@app.route("/discord")
def discord_redirect():
    return redirect("https://discord.gg/twmKh749aH")

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


@app.route("/instructor/class")
@require_login_role(Role.INSTRUCTOR)
def instructor_class():
    email = user_email()
    sched = [[s['id'], s['fields']] for s in airtable.get_class_automation_schedule() if s['fields']['Email'] == email]
    sched.sort(key=lambda s: s[1]['Start Time'])
    tz = pytz.timezone("US/Eastern")
    for sid, e in sched:
        date = dateparser.parse(e['Start Time']).astimezone(tz)

        # If it's in neon, fetch attendee info and generate a log URL
        if e.get('Neon ID'):
            e['attendees_for_log'] = []
            e['attendees'] = neon.fetch_attendees(e['Neon ID'])
            for a in e['attendees']:
                email = "unknown email"
                if a['accountId']:
                    acc = neon.fetch_account(a['accountId'])
                    if acc is not None:
                        email = acc.get('individualAccount', 
                                acc.get('companyAccount'))['primaryContact']['email1'] 
                    e['attendees_for_log'].append(f"{a['firstName']} {a['lastName']} ({email})")
                time.sleep(0.22) # API limits fetching to 5 per second

            print(f"Attendees for {e['Name (from Class)'][0]}:", e['attendees'])
            e['prefill'] = prefill_form(
                instructor=e['Instructor'],
                start_date=date,
                hours=e['Hours (from Class)'][0],
                class_name=e['Name (from Class)'][0],
                pass_emails=e['attendees_for_log'], 
                clearances=e['Form Name (from Clearance) (from Class)'],
                volunteer=e['Volunteer'],
                event_id=e['Neon ID'])

        for dateField in ('Confirmed', 'Instructor Log Date'):
            if e.get(dateField):
                e[dateField] = dateparser.parse(e[dateField])
        e['Dates'] = []
        for i in range(e['Days (from Class)'][0]):
            e['Dates'].append(date.strftime("%A %b %-d, %-I%p"))
            date += datetime.timedelta(days=7)
    return render_template("instructor_class.html", schedule=sched)

@app.route("/instructor/class/update", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_update():
    email = user_email()
    eid = request.form.get('eid')
    pub = request.form.get('pub') == 'true'
    return airtable.respond_class_automation_schedule(eid, pub).content

@app.route("/instructor/class/supply_req", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_supply_req():
    eid = request.form.get('eid')
    missing = request.form.get('missing') == 'true'
    return airtable.mark_schedule_supply_request(eid, missing).content

@app.route("/instructor/class/volunteer", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_volunteer():
    eid = request.form.get('eid')
    v = request.form.get('volunteer') == 'true'
    return airtable.mark_schedule_volunteer(eid, v).content

@app.route("/onboarding")
@require_login_role(Role.ONBOARDING)
def onboarding():
    return render_template("onboarding_wizard.html")

@app.route("/onboarding/check_membership")
@require_login_role(Role.ONBOARDING)
def onboarding_check_membership():
    email = request.args.get('email')
    m = neon.search_member(email.strip())
    print(m)
    return dict(
            neon_id=m['Account ID'],
            first=m['First Name'], 
            last=m['Last Name'], 
            status=m['Account Current Membership Status'], 
            level=m['Membership Level'],
            discord_user=m['Discord User'])

@app.route("/onboarding/coupon")
@require_login_role(Role.ONBOARDING)
def onboarding_create_coupon():
    email = request.args.get('email')
    m = neon.search_member(email.strip())
    code = f"NM-{m['Last Name'].upper()[:3]}{int(time.time())%1000}"
    print("Creating coupon code", code)
    return neon.create_coupon_code(code, 45)

@app.route("/onboarding/discord_member_add")
@require_login_role(Role.ONBOARDING)
def discord_member_add():
    name = request.args.get('name', '')
    neon_id = request.args.get('neon_id', '')
    nick = request.args.get('nick', '')
    if name == "" or neon_id == "" or nick == "":
        return "Require params: name, neon_id, nick"
    

    print(neon.set_discord_user(neon_id, name))

    client = discord_bot.get_client()
    result = asyncio.run_coroutine_threadsafe(
            client.grant_role(name, 'Members'),
            client.loop).result()
    if result == False:
        return "Failed to grant Members role: member not found"

    result = asyncio.run_coroutine_threadsafe(
            client.set_nickname(name, nick),
            client.loop).result()
    if result == False:
        return "Failed to set nickname: member not found"
    elif result == True:
        return "Setup complete"
    else:
        return result

@app.route("/tech_lead/techs_clearances")
@require_login_role(Role.SHOP_TECH_LEAD)
def techs_clearances():
    techs = []
    for t in neon.getMembersWithRole(Role.SHOP_TECH, [neon.CUSTOM_FIELD_CLEARANCES, neon.CUSTOM_FIELD_INTEREST]):
        clr = []
        if t.get('Clearances') is not None:
            clr = t['Clearances'].split('|')
        interest = t.get('Interest', '')
        techs.append(dict(
            id=t['Account ID'], 
            name=f"{t['First Name']} {t['Last Name']}", 
            interest=interest,
            clearances=clr))
    techs.sort(key=lambda t: len(t['clearances']))
    return render_template("techs_clearances.html", techs=techs)

@app.route("/shop_tech/handoff")
@require_login_role(Role.SHOP_TECH)
def shop_tech_handoff():
    shift_tasks = wiki.get_shop_tech_shift_tasks()
    return render_template("shop_tech_handoff.html", shift_tasks=shift_tasks)

@app.route("/shop_tech/profile", methods=["GET", "POST"])
@require_login_role(Role.SHOP_TECH)
def shop_tech_profile():
    user = session['neon_id']
    if request.method == "POST":
        interest = request.form['interest']
        neon.set_interest(user, interest)
        session['neon_account'] = neon.fetch_account(session['neon_id'])

    interest = ""
    for cf in session['neon_account']['individualAccount']['accountCustomFields']:
        if cf['name'] == 'Interest':
            interest = cf['value']
            break
    return render_template("shop_tech_profile.html", interest=interest)

@app.route("/admin/set_discord_nick")
@require_login_role(Role.ADMIN)
def set_discord_nick():
    name = request.args.get('name')
    nick = request.args.get('nick')
    if name == "" or nick == "":
        return "Bad argument: want ?name=foo&nick=bar"
    client = discord_bot.get_client()
    result = asyncio.run_coroutine_threadsafe(
            client.set_nickname(name, nick),
            client.loop).result()
    print(result)
    if result == False:
        return f"Member '{name}' not found"
    else:
        return f"Member '{name}' now nicknamed '{nick}'"

if __name__ == "__main__":
  import threading
  t = threading.Thread(target=discord_bot.run, daemon=True)
  t.start()
  app.run()
