from flask import Blueprint, request, render_template
from rbac import require_login_role, Role
from handlers.auth import user_email
from integrations import airtable, neon
import pytz
from dateutil import parser as dateparser
import datetime
import time

page = Blueprint('instructor', __name__, template_folder='templates')

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

@page.route("/instructor/class")
@require_login_role(Role.INSTRUCTOR)
def instructor_class():
    email = request.args.get('email')
    if email is not None:
        roles = get_roles()
        if roles is None or Role.ADMIN['name'] not in roles:
            return "Not Authorized"
    else:
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
                aemail = "unknown email"
                if a['accountId']:
                    acc = neon.fetch_account(a['accountId'])
                    if acc is not None:
                        aemail = acc.get('individualAccount', 
                                acc.get('companyAccount'))['primaryContact']['email1'] 
                    e['attendees_for_log'].append(f"{a['firstName']} {a['lastName']} ({aemail})")
                time.sleep(0.22) # API limits fetching to 5 per second

            print(f"Attendees for {e['Name (from Class)'][0]}:", e['attendees'])
            e['prefill'] = prefill_form(
                instructor=e['Instructor'],
                start_date=date,
                hours=e['Hours (from Class)'][0],
                class_name=e['Name (from Class)'][0],
                pass_emails=e['attendees_for_log'], 
                clearances=e['Form Name (from Clearance) (from Class)'],
                volunteer=e.get('Volunteer', False),
                event_id=e['Neon ID'])

        for dateField in ('Confirmed', 'Instructor Log Date'):
            if e.get(dateField):
                e[dateField] = dateparser.parse(e[dateField])
        e['Dates'] = []
        for i in range(e['Days (from Class)'][0]):
            e['Dates'].append(date.strftime("%A %b %-d, %-I%p"))
            date += datetime.timedelta(days=7)
    return render_template("instructor_class.html", 
            schedule=sched,
            now=datetime.datetime.now(),
            email=email)

@page.route("/instructor/class/update", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_update():
    email = user_email()
    eid = request.form.get('eid')
    pub = request.form.get('pub') == 'true'
    return airtable.respond_class_automation_schedule(eid, pub).content

@page.route("/instructor/class/supply_req", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_supply_req():
    eid = request.form.get('eid')
    missing = request.form.get('missing') == 'true'
    return airtable.mark_schedule_supply_request(eid, missing).content

@page.route("/instructor/class/volunteer", methods=["POST"])
@require_login_role(Role.INSTRUCTOR)
def instructor_class_volunteer():
    eid = request.form.get('eid')
    v = request.form.get('volunteer') == 'true'
    return airtable.mark_schedule_volunteer(eid, v).content

