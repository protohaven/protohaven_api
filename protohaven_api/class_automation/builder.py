""" Build and output a list of email and other communications for informing
 techs, instructors, and event registrants about their classes and events"""
import datetime
import logging
import pickle
from collections import defaultdict
from pathlib import Path

from dateutil import parser as dateparser

from protohaven_api.class_automation import email_templates as tmpl
from protohaven_api.integrations.airtable import (
    get_class_automation_schedule,
    get_emails_notified_after,
    get_instructor_email_map,
)
from protohaven_api.integrations.neon import (
    fetch_account,
    fetch_attendees,
    fetch_published_upcoming_events,
)


def get_account_email(account_id):
    """Gets the matching email for a Neon account, by ID"""
    content = fetch_account(account_id)
    if isinstance(content, list):
        raise RuntimeError(content)
    content = content.get("individualAccount", None) or content.get("companyAccount")
    content = content.get("primaryContact", {})
    return content.get("email1") or content.get("email2") or content.get("email3")


class ClassEmailBuilder:  # pylint: disable=too-many-instance-attributes
    """Builds emails and other notifications for class updates"""

    CACHE_FILE = "class_email_builder_cache.pkl"
    ignore_ovr = []  # @param {type:'raw'}
    confirm_ovr = []  # @param {type:'raw'}
    pro_bono_classes = []  # @param {type:'raw'}
    cancel_ovr = []  # @param {type:'raw'}
    ignore_email = []  # List of email destinations to ignore
    ignore_all_survey = False  # @param {type: 'boolean'}
    ignore_all_cancelled = False  # @param {type: 'boolean'}
    notify_techs = True  # @param {type:"boolean"}
    notify_instructors = True  # @param {type:"boolean"}
    notify_registrants = True  # @param {type:"boolean"}

    def __init__(self, log=logging.getLogger()):
        self.log = log
        self.for_techs = []  # [(url, name, capacity)]
        self.actionable_classes = []  # (evt, action)
        self.summary = defaultdict(lambda: {"action": set(), "targets": set()})
        self.output = []  # [{target, subject, body}]

        if Path(self.CACHE_FILE).exists():
            self.log.info(f"Loading from cache {self.CACHE_FILE}")
            with open(self.CACHE_FILE, "rb") as f:
                data = pickle.load(f)
            self.log.info(f"Cache date {data['date']}")
            self.for_techs = data["for_techs"]
            self.actionable_classes = data["actionable_classes"]
        else:
            self.events = list(fetch_published_upcoming_events())
            self.log.info(f"Fetched {len(self.events)} events fron Neon")
            self.log.debug(f"example data:\n{self.events[0]}")

            airtable_schedule = get_class_automation_schedule()
            self.airtable_schedule = {
                s["fields"]["Neon ID"]: s
                for s in airtable_schedule
                if s["fields"].get("Neon ID") is not None
            }
            self.log.info(
                f"Fetched {len(self.airtable_schedule)}) schedule items from Airtable"
            )
            self.log.debug(f"example data:\n{list(self.airtable_schedule.items())[0]}")
            self.email_map = get_instructor_email_map()
            self.log.info(f"Fetched {len(self.email_map)} instructor emails")

    def push_class(self, evt, action, reason):
        """Push a class onto the actionable list. It'll later be used in email templates"""
        self.log.info(f"{action}: {evt['name']} ({reason})")
        self.actionable_classes.append([evt, action])

    def handle_day_before(self, evt):
        """Handle day-before notifications for the event"""
        if evt["capacity"] == 0:
            self.log.info(f"Skipping for_techs (too full): {evt['name']}")
            return
        if evt["occupancy"] < 0.5 and not (
            evt["occupancy"] > 0 and evt["volunteer_instructor"]
        ):
            if self.ignore_all_cancelled:
                self.log.info(f"IGNORE {evt['name']} (ignore_all_cancelled=True)")
            else:
                self.push_class(
                    evt, "CANCEL", "not enough students and/or not pro bono"
                )
            return

        self.push_class(
            evt,
            "CONFIRM",
            "pro bono" if evt["volunteer_instructor"] else "instructor paid",
        )

        # Only add tech available classes if the class isn't yet full
        if evt["occupancy"] < 1.0:
            self.for_techs.append(evt)
            self.log.info(f"Added to for_techs: {evt['name']}")

    def handle_3days_before(self, evt):
        """Handle 3-days-until notifications for event."""
        # Only claim low occupancy shortly before the class if it's a
        # paid class
        if evt["occupancy"] < 0.5 and not evt["volunteer_instructor"]:
            self.push_class(evt, "LOW_ATTENDANCE_3DAYS", "not enough registrants")

    def handle_week_before(self, evt):
        """Handle week-before notifications for event"""
        if evt["occupancy"] < 0.5 and not evt["volunteer_instructor"]:
            self.push_class(evt, "LOW_ATTENDANCE_7DAYS", "not enough registrants")

    def handle_10days_before(self, evt):
        """Handle "10 days before" notifications for event"""
        if evt["supply_state"] == "Supply Check Needed":
            self.push_class(evt, "SUPPLY_CHECK_NEEDED", "supply check needed")

    def handle_after(self, evt):
        """Handle notifications for after event is run"""
        if self.ignore_all_survey:
            self.log.info(f"IGNORE {evt['name']} (ignore_all_survey=True)")
        elif evt["occupancy"] >= 0.5 or evt["volunteer_instructor"]:
            # Survey reminder only goes out if the class actually ran,
            # which we check indirectly via requirements to run (filled or volunteer)
            self.push_class(evt, "POST_RUN_SURVEY", "")

    def _annotate(self, evt):
        """Annotate an event with additional data needed to properly categorize it"""
        evt["python_date"] = dateparser.parse(evt["startDate"] + " " + evt["startTime"])
        evt["python_date_end"] = dateparser.parse(evt["endDate"] + " " + evt["endTime"])
        evt["attendees"] = fetch_attendees(evt["id"])
        for a in evt["attendees"]:
            email = get_account_email(
                a.get("registrantAccountId") or a.get("accountId")
            )
            if email is None:
                raise RuntimeError(f"Failed to resolve email for attendee: {a}")
            a["email"] = email.lower()

        evt["unique"] = {a["attendeeId"] for a in evt["attendees"]}
        evt["signups"] = len(evt["unique"])
        evt["occupancy"] = (
            0 if evt["capacity"] == 0 else evt["signups"] / evt["capacity"]
        )
        evt["need"] = (evt["capacity"] // 2) - evt["signups"]

        sched = self.airtable_schedule.get(str(evt["id"]))
        if sched is not None:
            sched = sched["fields"]
        else:
            sched = {}
        evt["volunteer_instructor"] = sched.get("Volunteer") or (
            evt["id"] in self.pro_bono_classes
        )
        evt["supply_state"] = sched.get("Supply State")
        evt["instructor_email"] = None
        for inst_name, inst_email in self.email_map.items():
            if inst_name.lower() in evt["name"].lower():
                evt["instructor_email"] = inst_email.lower()
                evt["instructor_firstname"] = inst_name.split()[0]
                break

        evt["already_notified"] = []  # assigned during sort
        return evt

    def _sort_events_for_notification(self, now):
        """Sort events into various notification buckets"""
        for evt in self.events:
            neon_id = evt["id"]
            if neon_id in self.ignore_ovr:
                self.log.info(f"IGNORE {evt['name']} (per override)")
                continue
            self.log.debug(f"sorting event {neon_id}")
            evt = self._annotate(evt)
            date = evt["python_date"]
            prior_10days = date - datetime.timedelta(days=11)
            prior_week = date - datetime.timedelta(days=8)
            prior_3days = date - datetime.timedelta(days=3)
            prior_day = date - datetime.timedelta(days=1, hours=10)

            if neon_id in self.confirm_ovr:
                self.push_class(evt, "CONFIRM", "per override")
            elif neon_id in self.cancel_ovr:
                self.push_class(evt, "CANCEL", "per override")
            elif now > evt["python_date_end"]:
                evt["already_notified"] = get_emails_notified_after(neon_id, date)
                self.log.info("after run survey notify")
                self.handle_after(evt)
            elif now >= prior_day:
                evt["already_notified"] = get_emails_notified_after(neon_id, prior_day)
                self.handle_day_before(evt)
            elif now >= prior_3days:
                evt["already_notified"] = get_emails_notified_after(
                    neon_id, prior_3days
                )
                self.handle_3days_before(evt)
            elif now >= prior_week:
                evt["already_notified"] = get_emails_notified_after(neon_id, prior_week)
                self.handle_week_before(evt)
            elif now >= prior_10days:
                evt["already_notified"] = get_emails_notified_after(
                    neon_id, prior_10days
                )
                self.handle_10days_before(evt)
            else:
                self.log.info(
                    f"IGNORE ({(date - now).days} day(s) out; too far): {evt['name']}"
                )
                continue

        self.log.info(f"{len(self.for_techs)} classes available for techs")
        for e in self.for_techs:
            self.log.info(
                f" - {e['id']} {e['name']} ({e['signups']} / {e['capacity']} seats filled)"
            )
        self.log.info(f"{len(self.actionable_classes)} Actionable classes")
        for e, action in self.actionable_classes:
            self.log.info(f" - {action} - {e['id']} {e['name']}")

    def _append(self, action, target, fn, evt, *args):
        """Append notification details onto the `output` list"""
        self.summary[evt["id"]]["name"] = evt["name"]
        self.summary[evt["id"]]["action"].add(action)
        self.summary[evt["id"]]["targets"].add(target)
        subject, body = fn(evt, *args)
        self.output.append(
            {"id": evt["id"], "target": target, "subject": subject, "body": body}
        )

    def _build_techs_notifications(self):
        """Build all notifications to techs; requires self.for_techs prepopulated"""
        if self.notify_techs and len(self.for_techs) > 0:
            filtered = []
            for evt in self.for_techs:
                if "#techs" in evt["already_notified"]:
                    self.log.info(
                        f"Skipping discord tech posting of {evt['name']}; already notified"
                    )
                    return
                self.summary[evt["id"]]["name"] = evt["name"]
                self.summary[evt["id"]]["targets"].add("#techs")
                self.summary[evt["id"]]["action"].add("NOTIFY_TECHS")
                filtered.append(evt)
            self._append(
                "NOTIFY_TECHS",
                "#techs",
                tmpl.techs_openings_msg,
                {"id": "multiple", "name": "multiple", "events": filtered},
            )

    def _build_instructor_notification(self, evt, action):
        """Build notification for instructors about `evt`"""
        if evt["instructor_email"] in evt["already_notified"]:
            self.log.debug(
                f"Skipping email to instructor {evt['instructor_firstname']}; already notified"
            )
            return
        if evt["instructor_email"].strip() in self.ignore_email:
            self.log.info(
                f"Skipping email to instructor {evt['instructor_firstname']} "
                f"({evt['instructor_email']}); ignored by override"
            )
            return
        target = f"Instructor ({evt['instructor_email']})"
        if action in ("LOW_ATTENDANCE_3DAYS", "LOW_ATTENDANCE_7DAYS"):
            self._append(action, target, tmpl.instructor_low_attendance_email, evt)
        elif action == "SUPPLY_CHECK_NEEDED":
            self._append(action, target, tmpl.instructor_check_supplies_email, evt)
        elif action == "CONFIRM":
            self._append(action, target, tmpl.instructor_class_confirmed_email, evt)
        elif action == "CANCEL":
            self._append(action, target, tmpl.instructor_class_cancelled_email, evt)
        elif action == "POST_RUN_SURVEY":
            self._append(action, target, tmpl.instructor_log_reminder_email, evt)
        else:
            raise RuntimeError("Unhandled instructor action:" + action)

    def _build_registrant_notification(self, evt, action, a):
        """Build notification for a registrant `a` about event `evt`"""
        if a["email"] in evt["already_notified"]:
            self.log.debug(
                f"Skipping email to attendee {a['firstName']} ({a['email']}); already notified"
            )
            return
        if a["email"].strip() in self.ignore_email:
            self.log.info(
                f"Skipping email to attendee {a['firstName']} ({a['email']}); ignored by override"
            )
            return

        target = f"{a['firstName']} {a['lastName']} ({a['email']})"
        if action in ("LOW_ATTENDANCE_7DAYS", "LOW_ATTENDANCE_3DAYS"):
            self._append(action, target, tmpl.registrant_low_attendance_email, evt, a)
        elif action == "CONFIRM":
            self._append(action, target, tmpl.registrant_class_confirmed_email, evt, a)
        elif action == "CANCEL":
            self._append(action, target, tmpl.registrant_class_cancelled_email, evt, a)
        elif action == "POST_RUN_SURVEY":
            self._append(
                action, target, tmpl.registrant_post_class_survey_email, evt, a
            )

    def build(self, now=None):  # pylint: disable=too-many-branches
        """Build all notifications and return them in a list"""
        if now is None:
            now = datetime.datetime.now()

        if len(self.actionable_classes) == 0:
            self.log.info("Sorting events...")
            self._sort_events_for_notification(now)
            self.log.info(f"Sorting complete, caching result in {self.CACHE_FILE}")
            with open(self.CACHE_FILE, "wb") as f:
                pickle.dump(
                    {
                        "date": now,
                        "for_techs": self.for_techs,
                        "actionable_classes": self.actionable_classes,
                    },
                    f,
                )
        else:
            self.log.warning("Skipping sort; using cache")

        events_missing_email = [
            (evt["id"], evt["name"], evt["python_date"])
            for evt, action in self.actionable_classes
            if evt.get("instructor_email") is None
        ]
        if len(events_missing_email) > 0:
            self.log.warning("Events missing instructor emails:")
            for eid, ename, edate in events_missing_email:
                self.log.warning(f"\t- {edate} #{eid} {ename}")
            self.log.warning(
                "Add them to instructor capabilities table: "
                "https://airtable.com/applultHGJxHNg69H/tbltv8tpiCqUnLTp4"
            )

        if self.notify_instructors:
            self.log.info("Building instructor notifications")
            for evt, action in self.actionable_classes:
                self._build_instructor_notification(evt, action)
        else:
            self.log.warning("Skipping instructor notifications")

        if self.notify_registrants:
            self.log.info("Building attendee notifications")
            for evt, action in self.actionable_classes:
                for a in evt["attendees"]:
                    self._build_registrant_notification(evt, action, a)
        else:
            self.log.warning("Skipping registrant notifications")

        self.log.info("Building summary notification")
        if len(self.summary) > 0:
            self._append(
                "SUMMARY",
                "#class-automation",
                tmpl.automation_summary_msg,
                {"id": "N/A", "name": "summary", "events": self.summary},
            )

        return self.output
