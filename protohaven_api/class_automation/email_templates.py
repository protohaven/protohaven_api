"""Message template functions for notifying instructors, techs, and event registrants"""
import datetime
from urllib.parse import quote


def techs_openings_msg(events):
    """Generate message for techs about classes with open seats"""
    events = events["events"]  # Unpack
    body = (
        f"Hey @Techs - there's {len(events)} class{'es' if len(events) != 1 else ''} "
        "available for backfill in the next 24 hours:\n"
    )
    for evt in events:
        url = f"https://protohaven.app.neoncrm.com/eventReg.jsp?event={evt['id']}&"
        body += (
            f"\n{evt['startDate']} {evt['startTime']} - {evt['name']} "
            f"({evt['capacity']-evt['signups']} "
            f"seat{'s' if evt['capacity']-evt['signups'] != 1 else ''} left): {url}"
            "\n\nReply to this message if you're interested in filling a slot."
            "\n\nFirst come, first served!"
        )
    return "New classes for tech backfill", body


def automation_summary_msg(summary):
    """Generate message summarizing messages sent to targets"""
    content = []
    for evtid, details in summary["events"].items():
        content.append(
            f"{'|'.join(list(details['action']))} #{evtid} "
            f"{details['name']}: notified {', '.join(details['targets'])}"
        )
    return "Automation notification summary", ("\n".join(content))


def instructor_update_calendar_email(name, start, end):
    """Generate message to instructor for confirming their availability"""
    firstname = name.split(" ")[0]
    subject = f"{firstname}: please confirm your teaching availability!"
    body = (
        f"Hi {firstname},"
        "\n\nThanks for your continued involvement at Protohaven!"
        f"\nWe will be scheduling classes very soon for the period of {start.strftime('%B %-d')} "
        f"through {end.strftime('%B %-d')}."
        "\n\nPlease take the following steps ASAP so we can schedule your classes:"
        "\n\n1. Click the calendar link below to open it in a new tab. It will open as read-only."
        '\n2. Click the "+Google Calendar" link at the very bottom right of the page to add it '
        "to your google calendar for editing."
        "\n3. Create calendar events describing your availability. It's important to use just "
        f"your full name ({name}) for the event name, and to set the date and time appropriately "
        "via the input boxes."
        "\n   Before saving your events, confirm you're adding it to the "
        '"Instructor Availability" calendar (the drop down is right below the '
        '"Add notification" button).'
        "\n\nNote that not all of your available times will be scheduled - and you'll get a "
        "chance to confirm specific proposed classes before they're made public."
        "\n\nHere's the calendar link:"
        "\nhttps://calendar.google.com/calendar/u/1?cid=Y19hYjA0OGUyMTgwNWEwYjVmN2YwOTRhODFmNmRiZDE5YTNjYmE1NTY1YjQwODk2MjU2NTY3OWNkNDhmZmQwMmQ5QGdyb3VwLmNhbGVuZGFyLmdvb2dsZS5jb20"  # pylint: disable=line-too-long
        "\n\nIf you need any help or have any questions, please reach out on the #instructors "
        "discord or to education@protohaven.org."
        "\n\nThanks!"
        "\n -Protohaven Automation"
    )
    return subject, body


def instructor_check_supplies_email(evt):
    """Generate message to instructors asking them to check supplies for an event"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]
    evt_date = evt["python_date"]

    subject = (
        f"{classname} on {evt_date.strftime('%B %-d')} - please confirm class supplies"
    )
    body = (
        f"Hi {firstname},"
        f"\n\nThanks for agreeing to teach {classname} on {evt_date.strftime('%B %-d')}."
        "\n\nThis is an automated reminder that you need to confirm there's adequate supplies "
        "at Protohaven to run your class."
        "\n\nPlease check the class supply room, then visit "
        'https://api.protohaven.org/instructor/class and click either "Supplies Needed"'
        ' or "Supplies OK" to indicate the supply state of your class.'
        "\n\nIf supplies are needed, make sure to submit a New Request via the same page "
        "or else they won't be purchased."
        "\n\nThanks!"
        "\n -Protohaven Automation"
    )
    return subject, body


def instructor_low_attendance_email(evt):
    """Generate message to instructor warning mentioning low attendance and asking
    for help improving"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]
    evt_date = evt["python_date"]
    signups = evt["signups"]
    capacity = evt["capacity"]

    subject = (
        f"{classname} on {evt_date.strftime('%B %-d')} - help us find {capacity-signups} "
        f"more student{'s' if capacity-signups != 1 else ''}!"
    )
    body = (
        f"Hi {firstname},"
        f"\n\nThanks for agreeing to teach {classname} on {evt_date.strftime('%B %-d')}."
        f"\n\nTo maximize your impact, we need your help to find {capacity-signups} "
        f"additional student{'s' if capacity-signups else ''} to take the class."
        "\n\nThere are a couple easy ways to do this:"
        "\n\n - Post about your class on social media (Instagram, Facebook, etc.) "
        "to raise awareness"
        "\n - Share your excitement in teaching a class to friends, family, coworkers, and "
        "anyone else you meet, and encourage them to sign up!"
        "\n\nIf you have any additional ideas for getting the word out there, please post them "
        "in the #instructors channel of our Discord."
        "\n\nThanks for supporting Protohaven as an instructor. Happy teaching!"
        "\n -Protohaven Automation"
    )
    return subject, body


def registrant_class_confirmed_email(evt, a):
    """Generate message to registrant that the class is confirmed to run"""
    firstname = a["firstName"]
    classname = evt["name"]
    evt_date = evt["python_date"]
    signups = evt["signups"]
    capacity = evt["capacity"]

    subject = f"Your class '{classname}' is on for {evt_date.strftime('%B %-d')}!"
    body = f"Hi {firstname},"
    body += f"\n\nGet excited! Your class {classname} "
    if signups > 1:
        body += f"has {signups} total students, and "
    body += f"will be running on {evt_date.strftime('%B %-d')}."
    days = (evt_date - datetime.datetime.now()).days
    if capacity > 0 and days > 1:
        body += (
            f"\n\nWe still have {capacity-signups} "
            f"seat{'s' if (capacity-signups) != 1 else ''} left, so invite your friends!"
        )
    body += (
        "\n\nPlease remember to wear appropriate clothing for the activity - this "
        "usually means close-toed shoes, with any long sleeves or hair pulled back."
        "\n\nIf you have any questions, please reach out to education@protohaven.org."
        "\n\nHope to see you in the shop soon!\nProtohaven Staff"
    )
    return subject, body


def instructor_class_confirmed_email(evt):
    """Generate message to instructor that the class is confirmed to run"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]
    evt_date = evt["python_date"]
    signups = evt["signups"]

    subject = f"{classname} is on for {evt_date.strftime('%B %-d')}!"
    body = (
        f"Hi {firstname},"
        f"\n\nGet excited! Your class {classname} has {signups} "
        f"student{'s' if signups != 1 else ''} and will "
        f"be running on {evt_date.strftime('%B %-d')}."
        "\n\nIf you have any questions, please reach out to education@protohaven.org."
        "\n\nHope to see you in the shop soon!\nProtohaven Staff"
    )
    return subject, body


def registrant_class_cancelled_email(evt, a):
    """Generate message to registrant that the class was cancelled"""
    firstname = a["firstName"]
    classname = evt["name"]
    evt_date = evt["python_date"]

    subject = f"Your class '{classname}' was cancelled"
    body = (
        f"Hi {firstname},"
        f"\n\nUnfortunately, we had to cancel your class {classname} (scheduled for "
        f"{evt_date.strftime('%B %-d')}). "
        "\n\nWe can either refund the full amount of the class, or offer class credit "
        "if you'd like to enroll in a different class."
        "\nPlease reach out to education@protohaven.org with your choice so we can "
        "start the process."
        "\n\nWe're sorry for the change of plans - it would have been great to have you. "
        "If you're still interested in classes and tool instruction, please check our "
        "event schedule at https://www.protohaven.org/classes."
        "\n\nHope to see you in the shop soon!\nProtohaven Staff"
    )
    return subject, body


def instructor_class_cancelled_email(evt):
    """Generate message to instructor that their class was cancelled"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]
    evt_date = evt["python_date"]

    subject = f"Your class '{classname}' was cancelled"
    body = (
        f"Hi {firstname},"
        f"\n\nUnfortunately, we had to cancel your class {classname} "
        f"(scheduled for {evt_date.strftime('%B %-d')}) as nobody signed up to take it."
        "\n\nIf you have any questions, please reach out to education@protohaven.org."
    )
    body += "\n\n'Till next time!\nProtohaven Staff"
    return subject, body


def registrant_post_class_survey_email(evt, a):
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
    body = (
        f"Hi {firstname},"
        "\n\nThanks again for taking a class with us! Your interest supports our instructors, "
        "and we hope it's helped you in your projects as well."
        "\n\nWe'd really appreciate any feedback you have, so we can improve the class for next "
        "time. If you have 5 minutes, please click on the survey link below - it's anonymously "
        "shared with your instructor when submitted:"
        f"\n\n{form_link}"
        "\n\nHope to see you again soon!\nProtohaven Staff"
    )
    return subject, body


def instructor_log_reminder_email(evt):
    """Generate message to instructor reminding them to log their hours"""
    firstname = evt["instructor_firstname"]
    classname = evt["name"]

    subject = f"{classname}: Please submit instructor log"
    body = (
        f"Hi {firstname},"
        "\n\nThis is a friendly reminder to submit your instructor log (if you haven't already) "
        "to receive payment for the class, and to grant clearances to students."
        '\n\nYou can do this in under a minute by clicking "Submit Log" for a pre-filled form '
        "for the specific class at https://api.protohaven.org/instructor/class."
        "\n\nIf you have any questions, please reach out to education@protohaven.org."
    )
    body += "\n\nThanks!\nProtohaven Automation"
    return subject, body


def email_instructor_update_calendar(name, start, end):
    """Sends a reminder to an instructor to update their availability calendar"""
    firstname = name.split(" ")[0]
    subject = f"{firstname}: please confirm your teaching availability!"
    body = f"Hi {firstname},"
    body += "\n\nThanks for your continued involvement at Protohaven!"
    body += (
        "\nWe will be scheduling classes very soon for the period of "
        f"{start.strftime('%B %-d')} through {end.strftime('%B %-d')}."
    )
    body += (
        "\n\nPlease take the following steps ASAP so we can schedule " "your classes:"
    )
    body += (
        "\n\n1. Click the calendar link below to open it in a new tab. "
        "It will open as read-only."
    )
    body += (
        '\n2. Click the "+Google Calendar" link at the very bottom '
        "right of the page to add it to your google calendar for editing."
    )
    body += (
        "\n3. Create calendar events describing your availability. It's "
        f"important to use just your full name ({name}) for the event name, "
        "and to set the date and time appropriately via the input boxes."
    )
    body += (
        "\n4. Before saving your events, confirm you're adding it to the "
        '"Instructor Availability" calendar (the drop down is right below '
        'the "Add notification" button).'
    )
    body += (
        "\n\nNote that not all of your available times will be scheduled "
        "- and you'll get a chance to confirm specific proposed classes "
        "before they're made public."
    )
    body += "\n\nHere's the calendar link:"
    body += "\nhttps://calendar.google.com/calendar/u/1?cid=Y19hYjA0OGUyMTgwNWEwYjVmN2YwOTRhODFmNmRiZDE5YTNjYmE1NTY1YjQwODk2MjU2NTY3OWNkNDhmZmQwMmQ5QGdyb3VwLmNhbGVuZGFyLmdvb2dsZS5jb20"  # pylint: disable=line-too-long
    body += (
        "\n\nIf you need any help or have any questions, please reach "
        "out on the #instructors discord or to education@protohaven.org."
    )
    body += "\n\nThanks!"
    body += "\n -Protohaven Automation"
    return subject, body
