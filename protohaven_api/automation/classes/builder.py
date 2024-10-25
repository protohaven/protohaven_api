""" Build and output a list of email and other communications for informing
 techs, instructors, and event registrants about their classes and events"""
import datetime
import logging
import pickle
import re
from collections import defaultdict
from enum import Enum
from pathlib import Path

from dateutil import parser as dateparser

from protohaven_api.config import tz, tznow  # pylint: disable=import-error
from protohaven_api.integrations import airtable, neon  # pylint: disable=import-error
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("class_automation.builder")


def get_account_email(account_id):
    """Gets the matching email for a Neon account, by ID"""
    content = neon.fetch_account(account_id)
    content = content.get("individualAccount", None) or content.get("companyAccount")
    content = content.get("primaryContact", {})
    return content.get("email1") or content.get("email2") or content.get("email3")


def gen_scheduling_reminders(start, end):
    """Builds a set of reminder emails for all instructors, plus #instructors notification
    to schedule additional classes"""
    results = []
    summary = defaultdict(lambda: {"action": set(), "targets": set()})

    summary[""]["name"] = "Scheduling reminder"
    summary[""]["action"].add("SEND")

    already_scheduled = defaultdict(bool)
    for cls in airtable.get_class_automation_schedule():
        d = dateparser.parse(cls["fields"]["Start Time"])
        if start <= d <= end:
            already_scheduled[cls["fields"]["Email"].lower()] = True
    log.info(
        f"Already scheduled for interval {start} - {end}: {set(already_scheduled.keys())}"
    )

    for name, email in airtable.get_instructor_email_map(
        require_teachable_classes=True
    ).items():
        if already_scheduled[email.lower()]:
            continue  # Don't nag folks that already have their classes set up

        firstname = name.split(" ")[0]
        results.append(
            Msg.tmpl(
                "instructor_schedule_classes",
                name=name,
                firstname=firstname,
                start=start,
                end=end,
                target=email,
            )
        )
        summary[""]["targets"].add(email)

    if len(results) > 0:
        results.append(
            Msg.tmpl(
                "class_automation_summary",
                events=summary["events"],
                target="#class-automation",
            )
        )
    return results


def gen_class_scheduled_alerts(scheduled_by_instructor):
    """Generate alerts about classes getting scheduled"""
    results = []

    def format_class(cls, inst=False):
        start = dateparser.parse(cls["fields"]["Start Time"])
        start = start.astimezone(tz)
        # print(cls)
        result = f"- {start.strftime('%b %d %Y, %-I%P')}: {cls['fields']['Name (from Class)'][0]}"
        if inst:
            result += f" ({cls['fields']['Instructor']})"
        return result

    details = {"action": ["SCHEDULE"], "targets": []}
    channel_class_list = []
    for inst, classes in scheduled_by_instructor.items():
        formatted = [format_class(c) for c in classes]
        formatted.sort()
        email = classes[0]["fields"]["Email"]
        results.append(
            Msg.tmpl(
                "class_scheduled",
                inst=inst,
                n=len(classes),
                formatted=formatted,
                target=email,
            )
        )
        details["targets"].append(email)
        channel_class_list += classes

    if len(results) > 0:
        channel_class_list.sort(
            key=lambda c: dateparser.parse(c["fields"]["Start Time"])
        )
        results.append(
            Msg.tmpl(
                "instructors_new_classes",
                formatted=[format_class(c, inst=True) for c in channel_class_list],
                target="#instructors",
            )
        )
        details["targets"].append("#instructors")
        details["name"] = f"{len(channel_class_list)} new classes"
        results.append(
            Msg.tmpl(
                "class_automation_summary",
                events={"": details},
                target="#class-automation",
            )
        )
    return results


class Action(Enum):
    """Actions describe what comms to send based on the state of an event
    and the current time relative to the event"""

    SUPPLY_CHECK_NEEDED = (
        10,
        7,
        lambda evt: evt["supply_state"] == "Supply Check Needed",
    )
    LOW_ATTENDANCE_7DAYS = (8, 3, lambda evt: evt["signups"] < 3)
    LOW_ATTENDANCE_3DAYS = (3, 1, lambda evt: evt["signups"] < 3)
    CONFIRM = (1, 0, lambda evt: evt["occupancy"] > 0)
    CANCEL = (1, 0, lambda evt: evt["occupancy"] == 0)
    FOR_TECHS = (1, 0, lambda evt: 0.1 < evt["occupancy"] < 0.9)
    POST_RUN_SURVEY = (0, -3, lambda evt: evt["occupancy"] > 0)

    def needed_for(self, evt, now):
        """Checkif action is needed for `evt` at time `now`"""
        date = evt["python_date"]
        # Only applies within the specific time band
        if date - datetime.timedelta(
            days=self.day_offset
        ) > now or now > date - datetime.timedelta(days=self.day_until):
            return False
        return self.need_fn(evt)

    def __init__(self, day_offset, day_until, need_fn):
        self.day_offset = day_offset
        self.day_until = day_until
        self.need_fn = need_fn


class ClassEmailBuilder:  # pylint: disable=too-many-instance-attributes
    """Builds emails and other notifications for class updates"""

    CACHE_FILE = "class_email_builder_cache.pkl"
    CACHE_EXPIRY_HOURS = 1

    # Events we know to not be useful when building emails
    BLOCKLIST = [
        3775,  # Equipment clearance
        17631,  # Private instruction
    ]

    ignore_ovr = []  # @param {type:'raw'}
    filter_ovr = []
    confirm_ovr = []  # @param {type:'raw'}
    pro_bono_classes = []  # @param {type:'raw'}
    ignore_email = []  # List of email destinations to ignore
    ignore_all_survey = False  # @param {type: 'boolean'}
    notify_techs = True  # @param {type:"boolean"}
    notify_instructors = True  # @param {type:"boolean"}
    notify_registrants = True  # @param {type:"boolean"}

    def __init__(self, _log=logging.getLogger(), use_cache=True):
        self.use_cache = use_cache
        self.log = _log
        self.for_techs = []
        self.actionable_classes = []  # (evt, action)
        self.summary = defaultdict(lambda: {"action": set(), "targets": set()})
        self.output = []  # [{target, subject, body}]
        self.events = []
        self.airtable_schedule = {}
        self.cache_loaded = False

    def fetch_and_aggregate_data(self, now):
        """Fetches and aggregates data from Neon and Airtable to use in notifying
        instructors and attendees about class status"""
        if Path(self.CACHE_FILE).exists() and self.use_cache:
            self.log.debug(f"Loading from cache {self.CACHE_FILE}")
            with open(self.CACHE_FILE, "rb") as f:
                data = pickle.load(f)
            self.log.debug(f"Cache date {data['date']}")
            if tznow() <= data["date"].astimezone(tz) + datetime.timedelta(
                hours=self.CACHE_EXPIRY_HOURS
            ):
                self.events = data["events"]
                self.airtable_schedule = data["schedule"]
                self.cache_loaded = True
                self.log.info("Cache is fresh; using it for event data")
                return

            self.log.info(
                f"Skipping cache; more than {self.CACHE_EXPIRY_HOURS} hour(s) old"
            )

        self.events = list(neon.fetch_published_upcoming_events())
        self.log.info(f"Fetched {len(self.events)} event(s) fron Neon")
        self.log.debug(" - ".join([e["name"] for e in self.events]))
        if len(self.events) > 0:
            self.log.debug(f"example data:\n{self.events[0]}")

        airtable_schedule = airtable.get_class_automation_schedule()
        self.airtable_schedule = {
            s["fields"]["Neon ID"]: s
            for s in airtable_schedule
            if s["fields"].get("Neon ID") is not None
        }
        self.log.info(
            f"Fetched {len(self.airtable_schedule)} schedule item(s) from Airtable"
        )
        if len(self.airtable_schedule) > 0:
            self.log.debug(f"example data:\n{list(self.airtable_schedule.items())[0]}")

        # Annotate
        for i, evt in enumerate(self.events):
            if i % 5 == 0:
                self.log.info(f"Annotated {i}/{len(self.events)} events")
            neon_id = evt["id"]
            if neon_id in self.BLOCKLIST:
                self.log.debug(f"Ignore annotating blocklist event {neon_id}")
                continue
            if str(neon_id) not in self.airtable_schedule:
                self.log.info(f"IGNORE #{neon_id} {evt['name']} (not in Airtable)")
                continue
            self._annotate(evt)  # Modified in-place
            self.log.debug(f"Annotated {neon_id}")

        if not self.cache_loaded and self.use_cache:
            self.log.info(f"Sorting complete, caching result in {self.CACHE_FILE}")
            with open(self.CACHE_FILE, "wb") as f:
                pickle.dump(
                    {
                        "date": now,
                        "events": self.events,
                        "schedule": self.airtable_schedule,
                    },
                    f,
                )

    def push_class(self, evt, action, reason=""):
        """Push a class onto the actionable list. It'll later be used in email templates"""
        self.log.info(f"{action}: {evt['name']} ({reason})")
        self.actionable_classes.append([evt, action])

    def notified(self, target, evt, day_offset):
        """Return true if the target was notified about the event within `day_offset` of event"""
        thresh = evt["python_date"] - datetime.timedelta(days=day_offset)
        prior_times = evt["notifications"].get(target, [])
        self.log.warning(
            f"{evt.get('id')} (on {evt['python_date']}): Looking up {target} "
            f"with day_offset={day_offset} in {prior_times}"
        )
        for t in prior_times:
            if t >= thresh:
                self.log.warning(
                    f"Found prior notification {t} within threshold {thresh}"
                )
                return True
        self.log.warning(f"Not notified after {thresh}")
        return False

    def _annotate(self, evt):
        """Annotate an event with additional data needed to properly categorize it"""
        evt["python_date"] = dateparser.parse(
            evt["startDate"] + " " + evt["startTime"]
        ).astimezone(tz)
        evt["python_date_end"] = dateparser.parse(
            evt["endDate"] + " " + evt["endTime"]
        ).astimezone(tz)
        # Only operate on attendees that successfully registered
        evt["attendees"] = [
            a
            for a in neon.fetch_attendees(evt["id"])
            if a["registrationStatus"] == "SUCCEEDED"
        ]
        if evt["capacity"] is None:
            evt["capacity"] = 0
        for a in evt["attendees"]:
            email = get_account_email(
                a.get("registrantAccountId") or a.get("accountId")
            )
            if email is None:
                raise RuntimeError(f"Failed to resolve email for attendee: {a}")
            a["email"] = email.lower()
            self.log.debug(f" - {a['firstName']} {a['lastName']} ({a['email']}) : {a}")

        evt["signups"] = len(
            {a["attendeeId"] for a in evt["attendees"]}
        )  # unique attendees
        evt["occupancy"] = (
            0 if evt["capacity"] == 0 else evt["signups"] / evt["capacity"]
        )
        evt["need"] = (evt["capacity"] // 2) - evt["signups"]

        sched = self.airtable_schedule.get(str(evt["id"]))
        evt["instructor_email"] = None
        evt["instructor_firstname"] = None
        if sched is not None:
            sched = sched["fields"]
            evt["instructor_email"] = sched["Email"]
            evt["instructor_firstname"] = sched["Instructor"].split()[0]
            evt["supply_cost"] = sched["Supply Cost (from Class)"][0]
        else:
            sched = {}
        evt["volunteer_instructor"] = sched.get("Volunteer") or (
            evt["id"] in self.pro_bono_classes
        )
        evt["supply_state"] = sched.get("Supply State")

        notify_thresh = evt["python_date"] - datetime.timedelta(days=14)
        evt["notifications"] = {
            k.lower(): v
            for k, v in airtable.get_notifications_after(
                re.compile(f".*{evt['id']}.*"), notify_thresh
            ).items()
        }
        return evt

    def _sort_event_for_notification(
        self, evt, now
    ):  # pylint: disable=too-many-branches
        """Sort events into various notification buckets"""
        neon_id = evt["id"]
        if neon_id in self.BLOCKLIST:
            return
        if str(neon_id) not in self.airtable_schedule:
            self.log.info(f"IGNORE #{neon_id} {evt['name']} (not in Airtable)")
            return

        self.log.debug(f"sorting event {neon_id}")
        if neon_id in self.ignore_ovr or (
            len(self.filter_ovr) > 0 and neon_id not in self.filter_ovr
        ):
            self.log.info(f"IGNORE {evt['name']} (override)")
            return

        if neon_id in self.confirm_ovr:
            self.push_class(evt, Action.CONFIRM, "override")
        else:
            for action in Action:
                if action.needed_for(evt, now):
                    self.push_class(evt, action)

    def _append(self, action, msg, evt):
        """Append notification details onto the `output` list"""
        if evt["id"]:
            msg.id = evt["id"]
        self.summary[evt["id"]]["name"] = evt["name"]
        self.summary[evt["id"]]["action"].add(str(action))
        self.summary[evt["id"]]["targets"].add(msg.target)
        if action == Action.CANCEL:
            msg.side_effect = {"cancel": evt["id"]}
        self.output.append(msg)

    def _build_techs_notifications(self, evt, action):
        """Build all notifications to techs; requires self.for_techs prepopulated"""
        if not self.notify_techs or action != Action.FOR_TECHS:
            return

        if self.notified("#techs", evt, action.day_offset):
            self.log.info(
                f"Skipping discord tech posting of {evt['name']}; already notified"
            )
            return

        # We don't append directly to self.output, instead aggregate so we can send a summary
        self.summary[evt["id"]]["name"] = evt["name"]
        self.summary[evt["id"]]["targets"].add("#techs")
        self.summary[evt["id"]]["action"].add(str(action))
        self.for_techs.append(evt)

    def _build_instructor_notification(self, evt, action):
        """Build notification for instructors about `evt`"""
        if self.notified(evt["instructor_email"], evt, action.day_offset):
            self.log.debug(
                f"Skipping email to instructor {evt['instructor_firstname']}; already notified"
            )
            return
        if evt["instructor_email"] is None:
            self.log.error(
                f"Could not build instructor notification for #{evt['id']} "
                f"{evt['name']} - no email given"
            )
            return
        if evt["instructor_email"].strip() in self.ignore_email:
            self.log.info(
                f"Skipping email to instructor {evt['instructor_firstname']} "
                f"({evt['instructor_email']}); ignored by override"
            )
            return
        tmpl = {
            Action.LOW_ATTENDANCE_7DAYS: "instructor_low_attendance",
            Action.SUPPLY_CHECK_NEEDED: "instructor_check_supplies",
            Action.CONFIRM: "instructor_class_confirmed",
            Action.CANCEL: "instructor_class_canceled",
            Action.POST_RUN_SURVEY: "instructor_log_reminder",
            Action.LOW_ATTENDANCE_3DAYS: None,
            Action.FOR_TECHS: None,
        }[action]
        if tmpl:
            self._append(
                action,
                Msg.tmpl(
                    tmpl, target=f"Instructor ({evt['instructor_email']})", evt=evt
                ),
                evt,
            )

    def _build_registrant_notification(self, evt, action, a):
        """Build notification for a registrant `a` about event `evt`"""
        if self.notified(a["email"], evt, action.day_offset):
            self.log.debug(
                f"Skipping email to attendee {a['firstName']} ({a['email']}); already notified"
            )
            return
        if a["email"].strip() in self.ignore_email:
            self.log.info(
                f"Skipping email to attendee {a['firstName']} ({a['email']}); ignored by override"
            )
            return
        tmpl = {
            Action.CONFIRM: "registrant_class_confirmed",
            Action.CANCEL: "registrant_class_canceled",
            Action.POST_RUN_SURVEY: "registrant_post_class_survey",
            Action.LOW_ATTENDANCE_7DAYS: None,
            Action.LOW_ATTENDANCE_3DAYS: None,
            Action.SUPPLY_CHECK_NEEDED: None,
            Action.FOR_TECHS: None,
        }[action]
        if tmpl:
            self._append(
                action,
                Msg.tmpl(
                    tmpl,
                    target=f"{a['firstName']} {a['lastName']} ({a['email']})",
                    evt=evt,
                    a=a,
                    now=tznow(),
                ),
                evt,
            )

    def build(self, now=None):  # pylint: disable=too-many-branches
        """Build all notifications and return them in a list"""
        if now is None:
            now = tznow()
        self.fetch_and_aggregate_data(now)

        self.log.info("Sorting events...")
        for evt in self.events:
            try:
                self._sort_event_for_notification(evt, now)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to sort event {evt['id']} - {evt['name']}"
                ) from e

        self.log.info(f"{len(self.for_techs)} classes available for techs")
        for e in self.for_techs:
            self.log.info(
                f" - {e['id']} {e['name']} ({e['signups']} / {e['capacity']} seats filled)"
            )
        self.log.info(f"{len(self.actionable_classes)} Actionable classes")
        for e, action in self.actionable_classes:
            self.log.info(f" - {action} - {e['id']} {e['name']}")

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

        if self.notify_techs:
            self.log.info("Building techs notifications")
            for evt, action in self.actionable_classes:
                if action == Action.FOR_TECHS:
                    self._build_techs_notifications(evt, action)
            # We need to append the built summary
            if len(self.for_techs) > 0:
                self._append(
                    str(Action.FOR_TECHS),
                    Msg.tmpl("tech_openings", events=self.for_techs, target="#techs"),
                    {
                        "id": ",".join([str(e["id"]) for e in self.for_techs]),
                        "name": "multiple",
                        "events": self.for_techs,
                    },
                )

        self.log.info("Building summary notification")
        if len(self.summary) > 0:
            self._append(
                "SUMMARY",
                Msg.tmpl(
                    "class_automation_summary",
                    events=self.summary,
                    target="#class-automation",
                ),
                {"id": "N/A", "name": "summary", "events": self.summary},
            )

        return self.output
