"""Build and output a list of email and other communications for informing
techs, instructors, and event registrants about their classes and events"""

import datetime
import locale
import logging
import re
import threading
from collections import defaultdict
from enum import Enum
from functools import lru_cache

from typings import Any

from protohaven_api.automation.classes import events as eauto
from protohaven_api.config import (  # pylint: disable=import-error
    safe_parse_datetime,
    tz,
    tznow,
)
from protohaven_api.integrations import (  # pylint: disable=import-error
    airtable,
    neon_base,
)
from protohaven_api.integrations.airtable import InstructorID, ScheduledClass
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("class_automation.builder")

LOCALE_LOCK = threading.Lock()


@lru_cache(maxsize=30)
def get_account_email(account_id):
    """Gets the matching email for a Neon account, by ID"""
    a = neon_base.fetch_account(account_id)
    if a:
        return a.email
    raise RuntimeError(f"Failed to resolve email for attendee: {account_id}")


def get_unscheduled_instructors(start, end, require_active=True):
    """Builds a set of instructors that do not have classes proposed or scheduled
    between `start` and `end`."""
    # Ensure start and end are timezone-aware
    if start.tzinfo is None or start.tzinfo.utcoffset(start) is None:
        start = start.replace(tzinfo=tz)
    if end.tzinfo is None or end.tzinfo.utcoffset(end) is None:
        end = end.replace(tzinfo=tz)

    already_scheduled = defaultdict(bool)
    for cls in airtable.get_class_automation_schedule():
        d = safe_parse_datetime(cls["fields"]["Start Time"])
        if start <= d <= end:
            already_scheduled[cls["fields"]["Email"].lower()] = True
    log.info(
        f"Already scheduled for interval {start} - {end}: {set(already_scheduled.keys())}"
    )
    for name, email in airtable.get_instructor_email_map(
        require_teachable_classes=True,
        require_active=require_active,
    ).items():
        if already_scheduled[email.lower().strip()]:
            continue  # Don't nag folks that already have their classes set up
        yield (name, email)


def gen_class_scheduled_alerts(
    scheduled_by_instructor: dict[InstructorID, list[ScheduledClass]],
):
    """Generate alerts about classes getting scheduled"""
    results = []

    def _fmt(c, inst):
        # Out of an abundance of paranoia, we lock incase there's a competing
        # thread setting the locale.
        with LOCALE_LOCK:
            locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
            return {
                "t": c.start_time,
                "start": c.start_time.strftime("%b %d %Y, %-I%p"),
                "name": c.name,
                "inst": c.instructor_name if inst else None,
            }

    details: dict[str, Any] = {"action": ["SCHEDULE"], "targets": []}
    channel_class_list: list[ScheduledClass] = []
    for inst, classes in scheduled_by_instructor.items():
        assert len(classes) > 0
        classes.sort(key=lambda c: c.start_time)
        results.append(
            Msg.tmpl(
                "class_scheduled",
                inst=inst,
                n=len(classes),
                formatted=[_fmt(c, inst=False) for c in classes],
                target=classes[0].instructor_email,
            )
        )
        details["targets"].append(classes[0].instructor_email)
        channel_class_list += classes

    if len(results) > 0:
        channel_class_list.sort(key=lambda c: c.start_time)
        results.append(
            Msg.tmpl(
                "instructors_new_classes",
                n=len(channel_class_list),
                classes=[_fmt(c, inst=True) for c in channel_class_list],
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
        lambda evt: evt.supply_state == "Supply Check Needed",
    )
    LOW_ATTENDANCE_7DAYS = (8, 3, lambda evt: evt.attendee_count < 3)
    LOW_ATTENDANCE_3DAYS = (3, 1, lambda evt: evt.attendee_count < 3)
    CONFIRM = (1, 0, lambda evt: evt.occupancy > 0)
    CANCEL = (1, 0, lambda evt: evt.occupancy == 0)
    FOR_TECHS = (1, 0, lambda evt: 0.1 < evt.occupancy < 0.9)
    POST_RUN_SURVEY = (0, -3, lambda evt: evt.occupancy > 0)

    def needed_for(self, evt, now):
        """Checkif action is needed for `evt` at time `now`"""
        date = evt.start_date
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

    def __init__(self, _log=logging.getLogger()):
        self.log = _log
        self.for_techs = []
        self.actionable_classes = []  # (evt, action)
        self.summary = defaultdict(lambda: {"action": set(), "targets": set()})
        self.output = []  # [{target, subject, body}]
        self.events = []
        self.notifications_by_class = {}
        self.attendee_emails = {}
        self.published = True
        self.ignore_ovr = []
        self.filter_ovr = []
        self.confirm_ovr = []

    def fetch_and_aggregate_data(self):
        """Fetches and aggregates data from Neon and Airtable to use in notifying
        instructors and attendees about class status"""
        self.events = []
        for evt in eauto.fetch_upcoming_events(
            published=self.published, merge_airtable=True, fetch_attendees=True
        ):
            if evt.in_blocklist():
                self.log.debug(f"Ignore annotating blocklist event {evt.neon_id}")
                continue
            self.events.append(evt)
            self.notifications_by_class[evt.neon_id] = {
                k.lower(): v
                for k, v in airtable.get_notifications_after(
                    re.compile(f".*{evt.neon_id}.*"),
                    evt.start_date - datetime.timedelta(days=14),
                ).items()
            }
            for a in evt.attendees:
                self.attendee_emails[a.neon_id] = get_account_email(a.neon_id)
            self.log.debug(f"Annotated {evt.neon_id}")
        self.log.info(f"Fetched and annotated {len(self.events)} event(s) fron Neon")

    def push_class(self, evt, action, reason=""):
        """Push a class onto the actionable list. It'll later be used in email templates"""
        self.log.info(f"{action}: {evt.name} ({reason})")
        self.actionable_classes.append([evt, action])

    def notified(self, target, evt, day_offset):
        """Return true if the target was notified about the event within `day_offset` of event"""
        thresh = evt.start_date - datetime.timedelta(days=day_offset)
        for t in self.notifications_by_class.get(evt.neon_id, {}).get(target, []):
            if t >= thresh:
                return True
        return False

    def _sort_event_for_notification(
        self, evt, now
    ):  # pylint: disable=too-many-branches
        """Sort events into various notification buckets"""
        log.info(f"Sort event {evt.name}")
        if evt.in_blocklist():
            return
        if not evt.airtable_data:
            self.log.info(f"IGNORE #{evt.neon_id} {evt.name} (not in Airtable)")
            return

        if evt.neon_id in self.ignore_ovr or (
            len(self.filter_ovr) > 0 and evt.neon_id not in self.filter_ovr
        ):
            self.log.info(f"IGNORE {evt.name} (override)")
            return

        if evt.neon_id in self.confirm_ovr:
            self.push_class(evt, Action.CONFIRM, "override")
        else:
            log.info(
                f"Checking actions needed for #{evt.neon_id} {evt.name} "
                f"({evt.attendee_count} attendees)"
            )
            for action in Action:
                if action.needed_for(evt, now):
                    log.info(f"Pushing action {action} for class {evt.name}")
                    self.push_class(evt, action)

    def _append(self, action, msg, evt_id, name):
        """Append notification details onto the `output` list"""
        msg.id = evt_id
        self.summary[evt_id]["name"] = name
        self.summary[evt_id]["action"].add(str(action))
        self.summary[evt_id]["targets"].add(msg.target)
        if action == Action.CANCEL:
            msg.side_effect = {"cancel": evt_id}
        self.output.append(msg)

    def _build_techs_notifications(self, evt, action):
        """Build all notifications to techs; requires self.for_techs prepopulated"""
        if action != Action.FOR_TECHS:
            return

        if self.notified("#techs", evt, action.day_offset):
            self.log.info(
                f"Skipping discord tech posting of {evt.name}; already notified"
            )
            return

        # We don't append directly to self.output, instead aggregate so we can send a summary
        self.summary[evt.neon_id]["name"] = evt.name
        self.summary[evt.neon_id]["targets"].add("#techs")
        self.summary[evt.neon_id]["action"].add(str(action))
        self.for_techs.append(evt)

    def _build_instructor_notification(self, evt, action):
        """Build notification for instructors about `evt`"""
        if self.notified(evt.instructor_email, evt, action.day_offset):
            self.log.debug(
                f"Skipping email to instructor {evt.instructor_name}; already notified"
            )
            return
        if evt.instructor_email is None:
            self.log.error(
                f"Could not build instructor notification for #{evt.neon_id} "
                f"{evt.name} - no email given"
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
                Msg.tmpl(tmpl, target=f"Instructor ({evt.instructor_email})", evt=evt),
                evt.neon_id,
                evt.name,
            )

    def _build_registrant_notification(self, evt, action, a):
        """Build notification for a registrant `a` about event `evt`"""
        if a.email is None:
            self.log.error(f"Skipping email to attendee {a.fname}; no email given")
            return
        if self.notified(a.email, evt, action.day_offset):
            self.log.debug(
                f"Skipping email to attendee {a.fname} ({a.email}); already notified"
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
                    target=f"{a.name} ({a.email})",
                    evt=evt,
                    a=a,
                    now=tznow(),
                ),
                evt.neon_id,
                evt.name,
            )

    def _build_notifications(self):
        self.log.info("Building instructor notifications")
        for evt, action in self.actionable_classes:
            self._build_instructor_notification(evt, action)

        self.log.info("Building attendee notifications")
        for evt, action in self.actionable_classes:
            for a in evt.attendees:
                self._build_registrant_notification(evt, action, a)

        self.log.info("Building techs notifications")
        for evt, action in self.actionable_classes:
            if action == Action.FOR_TECHS:
                self._build_techs_notifications(evt, action)

        if len(self.for_techs) > 0:
            self._append(
                str(Action.FOR_TECHS),
                Msg.tmpl("tech_openings", events=self.for_techs, target="#techs"),
                evt_id=",".join([str(e.neon_id) for e in self.for_techs]),
                name="multiple",
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
                evt_id="N/A",
                name="summary",
            )

    def build(self, now=None):  # pylint: disable=too-many-branches
        """Build all notifications and return them in a list"""
        if now is None:
            now = tznow()
        self.fetch_and_aggregate_data()

        self.log.info("Sorting events...")
        for evt in self.events:
            try:
                self._sort_event_for_notification(evt, now)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to sort event {evt.neon_id} - {evt.name}"
                ) from e

        self.log.info(f"{len(self.for_techs)} classes available for techs")
        for evt in self.for_techs:
            self.log.info(
                f" - {evt.neon_id} {evt.name} ({evt.attendee_count} / {evt.capacity} seats filled)"
            )

        self.log.info(f"{len(self.actionable_classes)} actionable classes")
        for evt, action in self.actionable_classes:
            self.log.info(f" - {action} - {evt.neon_id} {evt.name}")

        events_missing_email = [
            f"\t- {evt.start_date} #{evt.neon_id} {evt.name}"
            for evt, action in self.actionable_classes
            if evt.instructor_email is None
        ]
        if len(events_missing_email) > 0:
            self.log.warning("Events missing instructor emails:")
            for miss in events_missing_email:
                self.log.warning(miss)
            self.log.warning(
                "Add them to instructor capabilities table: "
                "https://airtable.com/applultHGJxHNg69H/tbltv8tpiCqUnLTp4"
            )

        self._build_notifications()
        return self.output
