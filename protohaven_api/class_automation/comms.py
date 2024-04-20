"""Message template functions for notifying instructors, techs, and event registrants"""
from urllib.parse import quote

from jinja2 import Environment, PackageLoader, select_autoescape

from protohaven_api.config import tznow  # pylint: disable=import-error

env = Environment(
    loader=PackageLoader("protohaven_api.class_automation"),
    autoescape=select_autoescape(),
)


def techs_openings(events):
    """Generate message for techs about classes with open seats"""
    ee = []
    for evt in events["events"]:
        ee.append(
            {
                "id": str(evt["id"]),
                "start": evt["python_date"].strftime("%B %-d, %-I%p"),
                "name": evt["name"],
                "avail": evt["capacity"] - evt["signups"],
            }
        )
    subject = "**New classes for tech backfill:**"
    return subject, env.get_template("tech_openings.jinja2").render(
        events=ee,
        n=len(ee),
    )


def automation_summary(summary):
    """Generate message summarizing messages sent to targets"""
    content = []
    for evtid, details in summary["events"].items():
        content.append(
            f"{'|'.join(list(details['action']))} #{evtid} "
            f"{details['name']}: notified {', '.join(details['targets'])}"
        )
    return "Automation notification summary", ("\n".join(content))


def instructor_update_calendar(name, start, end):
    """Generate message to instructor for confirming their availability"""
    firstname = name.split(" ")[0]
    subject = f"{firstname}: please confirm your teaching availability!"
    return subject, env.get_template("instructor_update_calendar.jinja2").render(
        name=name,
        firstname=firstname,
        start=start.strftime("%B %-d"),
        end=end.strftime("%B %-d"),
    )


def instructor_check_supplies(evt):
    """Generate message to instructors asking them to check supplies for an event"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]
    evt_date = evt["python_date"].strftime("%B %-d")

    subject = f"{classname} on {evt_date} - please confirm class supplies"
    return subject, env.get_template("instructor_check_supplies.jinja2").render(
        firstname=firstname, classname=classname, evt_date=evt_date
    )


def instructor_low_attendance(evt):
    """Generate message to instructor warning mentioning low attendance and asking
    for help improving"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]
    evt_date = evt["python_date"].strftime("%B %-d")
    avail = evt["capacity"] - evt["signups"]

    subject = (
        f"{classname} on {evt_date} - help us find {avail} "
        f"more student{'s' if avail != 1 else ''}!"
    )
    return subject, env.get_template("instructor_low_attendance.jinja2").render(
        firstname=firstname,
        classname=classname,
        evt_date=evt_date,
        avail=avail,
    )


def registrant_class_confirmed(evt, a, now=None):
    """Generate message to registrant that the class is confirmed to run"""
    if not now:
        now = tznow()
    firstname = a["firstName"]
    classname = evt["name"]
    evt_date = evt["python_date"].strftime("%B %-d")
    signups = evt["signups"]
    capacity = evt["capacity"]

    subject = f"Your class '{classname}' is on for {evt_date}!"
    return subject, env.get_template("registrant_class_confirmed.jinja2").render(
        firstname=firstname,
        classname=classname,
        evt_date=evt_date,
        signups=signups,
        capacity=capacity,
        days=(evt["python_date"] - now).days,
    )


def instructor_class_confirmed(evt):
    """Generate message to instructor that the class is confirmed to run"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]
    evt_date = evt["python_date"].strftime("%B %-d")
    signups = evt["signups"]

    subject = f"{classname} is on for {evt_date}!"
    return subject, env.get_template("instructor_class_confirmed.jinja2").render(
        firstname=firstname,
        classname=classname,
        evt_date=evt_date,
        signups=signups,
    )


def registrant_class_cancelled(evt, a):
    """Generate message to registrant that the class was cancelled"""
    firstname = a["firstName"]
    classname = evt["name"]
    evt_date = evt["python_date"].strftime("%B %-d")

    subject = f"Your class '{classname}' was cancelled"
    return subject, env.get_template("registrant_class_canceled.jinja2").render(
        firstname=firstname,
        classname=classname,
        evt_date=evt_date,
    )


def instructor_class_cancelled(evt):
    """Generate message to instructor that their class was cancelled"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]
    evt_date = evt["python_date"].strftime("%B %-d")

    subject = f"Your class '{classname}' was cancelled"
    return subject, env.get_template("instructor_class_canceled.jinja2").render(
        firstname=firstname,
        classname=classname,
        evt_date=evt_date,
    )


def registrant_post_class_survey(evt, a):
    """Generate message to registrant asking them to give feedback"""
    firstname = a["firstName"]
    email = a["email"]
    classname = evt["name"]
    evt_date = evt["python_date"]

    form_link = (
        f"https://docs.google.com/forms/d/e/1FAIpQLSdtXYv4RmtiTeyXAgc98fkgagpDX7wcWRC_S3P"
        "--z20yFFyMg/viewform?usp=pp_url"
        f"&entry.1721595896={quote(classname)}"
        f"&entry.139457221={quote(evt_date.strftime('%Y-%m-%d'))}"
        f"&entry.1361715406={quote(firstname)}"
        f"&entry.1141790460={quote(email)}"
        f"&entry.2026118127={id}"
    )
    subject = f"{classname}: Please share feedback"
    return subject, env.get_template("registrant_post_class_survey.jinja2").render(
        firstname=firstname,
        form_link=form_link,
    )


def instructor_log_reminder(evt):
    """Generate message to instructor reminding them to log their hours"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]
    subject = f"{classname}: Please submit instructor log"
    return subject, env.get_template("instructor_log_reminder.jinja2").render(
        firstname=firstname
    )
