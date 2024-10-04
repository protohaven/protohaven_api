"""Message template functions for notifying instructors, techs, and event registrants"""
from urllib.parse import quote

from protohaven_api.comms_templates import render
from protohaven_api.config import tznow  # pylint: disable=import-error


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
                "supply_cost": evt.get("supply_cost", 0),
            }
        )
    return render("tech_openings", events=ee, n=len(ee))


def automation_summary(summary):
    """Generate message summarizing messages sent to targets"""
    content = []
    for evtid, details in summary["events"].items():
        content.append(
            f"{'|'.join(list(details['action']))} #{evtid} "
            f"{details['name']}: notified {', '.join(details['targets'])}"
        )
    return "Automation notification summary", ("\n".join(content)), False


def instructor_schedule_classes(name, start, end):
    """Generate message to instructor reminding them to propose classes"""
    firstname = name.split(" ")[0]
    return render(
        "instructor_schedule_classes",
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
    return render(
        "instructor_check_supplies",
        firstname=firstname,
        classname=classname,
        evt_date=evt_date,
    )


def instructor_low_attendance(evt):
    """Generate message to instructor warning mentioning low attendance and asking
    for help improving"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]
    evt_date = evt["python_date"].strftime("%B %-d")
    avail = evt["capacity"] - evt["signups"]

    return render(
        "instructor_low_attendance",
        firstname=firstname,
        classname=classname,
        evt_date=evt_date,
        avail=avail,
    )


def registrant_class_confirmed(evt, a, now=None):
    """Generate message to registrant that the class is confirmed to run"""
    now = now or tznow()
    return render(
        "registrant_class_confirmed",
        firstname=a["firstName"],
        classname=evt["name"],
        evt_date=evt["python_date"].strftime("%B %-d"),
        signups=evt["signups"],
        capacity=evt["capacity"],
        days=(evt["python_date"] - now).days,
    )


def instructor_class_confirmed(evt):
    """Generate message to instructor that the class is confirmed to run"""
    return render(
        "instructor_class_confirmed",
        firstname=evt["instructor_firstname"],
        classname=evt["name"],
        evt_date=evt["python_date"].strftime("%B %-d"),
        signups=evt["signups"],
    )


def registrant_class_cancelled(evt, a):
    """Generate message to registrant that the class was cancelled"""
    return render(
        "registrant_class_canceled",
        firstname=a["firstName"],
        classname=evt["name"],
        evt_date=evt["python_date"].strftime("%B %-d"),
    )


def instructor_class_cancelled(evt):
    """Generate message to instructor that their class was cancelled"""
    return render(
        "instructor_class_canceled",
        firstname=evt["instructor_firstname"],
        classname=evt["name"],
        evt_date=evt["python_date"].strftime("%B %-d"),
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
    return render(
        "registrant_post_class_survey",
        classname=classname,
        firstname=firstname,
        form_link=form_link,
    )


def instructor_log_reminder(evt):
    """Generate message to instructor reminding them to log their hours"""
    return render(
        "instructor_log_reminder",
        firstname=evt["instructor_firstname"],
        classname=evt["name"],
    )
