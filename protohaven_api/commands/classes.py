"""Commands related to classes in Neon and Airtable"""
import argparse
import datetime
import logging
import re
from collections import defaultdict
from functools import lru_cache

import markdown
from dateutil import parser as dateparser

from protohaven_api.class_automation import builder, scheduler
from protohaven_api.commands.decorator import arg, command, load_yaml, print_yaml
from protohaven_api.commands.reservations import reservation_dict_from_record
from protohaven_api.config import tz, tznow  # pylint: disable=import-error
from protohaven_api.integrations import airtable, neon  # pylint: disable=import-error

log = logging.getLogger("cli.classes")


class Commands:
    """Commands for managing classes in Airtable and Neon"""

    @command(
        arg(
            "--start",
            help="start date for calendar reminder window",
            type=str,
        ),
        arg(
            "--end",
            help="end date for calendar reminder window",
            type=str,
        ),
    )
    def gen_instructor_schedule_reminder(self, args):
        """Reads the list of instructors from Airtable and generates
        reminder comms to all instructors, plus the #instructors discord,
        to propose additional class scheduling times"""
        if args.start:
            start = dateparser.parse(args.start).astimezone(tz)
        else:
            start = tznow() + datetime.timedelta(days=30)
        if args.end:
            end = dateparser.parse(args.end).astimezone(tz)
        else:
            end = start + datetime.timedelta(days=60)
        result = builder.gen_scheduling_reminders(start, end)
        print_yaml(result)
        log.info(f"Generated {len(result)} notification(s)")

    @command(
        arg(
            "--confirm",
            help="class IDs to auto-confirm when generating emails",
            type=int,
            nargs="+",
        ),
        arg(
            "--cancel",
            help="class IDs to auto-cancel when generating emails",
            type=int,
            nargs="+",
        ),
        arg(
            "--ignore",
            help="class IDs to ignore when generating emails",
            type=int,
            nargs="+",
        ),
        arg(
            "--filter",
            help="class IDs to restrict processing to when generating emails",
            type=int,
            nargs="+",
        ),
    )
    def gen_class_emails(self, args):
        """Reads schedule of classes from Neon and Airtable and outputs
        a list of emails to send to instructors, techs, and students.
        This does not actually send the emails; for that, see send_comms."""
        b = builder.ClassEmailBuilder(logging.getLogger("cli.email_builder"))
        b.ignore_ovr = args.ignore or []
        b.cancel_ovr = args.cancel or []
        b.confirm_ovr = args.confirm or []
        b.filter_ovr = args.filter or []
        # Add the rest here as needed

        result = b.build()
        print_yaml(result)
        log.info(f"Generated {len(result)} notification(s)")

    @command(
        arg(
            "--start",
            help="Start date (yyyy-mm-dd)",
            type=str,
            required=True,
        ),
        arg(
            "--end",
            help="End date (yyyy-mm-dd)",
            type=str,
            required=True,
        ),
        arg(
            "--filter",
            help="CSV of subset instructors to filter scheduling to",
            type=str,
            required=False,
        ),
    )
    def build_scheduler_env(self, args):
        """Construct an environment for assigning classes at times to instructors"""
        start = dateparser.parse(args.start).astimezone(tz)
        end = dateparser.parse(args.end).astimezone(tz)
        inst = {a.strip() for a in args.filter.split(",")} if args.filter else None
        env = scheduler.generate_env(start, end, inst)
        print_yaml(env)

    @command(
        arg(
            "--path",
            help="path to env file",
            type=str,
            required=True,
        )
    )
    def run_scheduler(self, args):
        """Run the class scheduler on a provided env"""
        env = load_yaml(args.path)
        instructor_classes, final_score = scheduler.solve_with_env(env)
        log.info(f"Final score: {final_score}")
        print_yaml(instructor_classes)

    @command(
        arg(
            "--path",
            help="path to schedule file",
            type=str,
            required=True,
        ),
        arg(
            "--apply",
            help="Actually append",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def append_schedule(self, args):
        """Adds a schedule (created with `run_scheduler`) to Airtable for
        instructor confirmation."""
        sched = load_yaml(args.path)
        notifications = list(scheduler.gen_schedule_push_notifications(sched))
        if args.apply:
            scheduler.push_schedule(sched)
        print_yaml(notifications)

    @command(
        arg(
            "--id",
            help="class IDs to cancel",
            type=str,
            nargs="+",
        )
    )
    def cancel_classes(self, args):
        """cancel passed classes by unpublishing and disabling registration"""
        for i in args.id:
            i = i.strip()
            log.info(f"Cancelling #{i}")
            neon.set_event_scheduled_state(i, scheduled=False)
        log.info("Done")

    def _apply_pricing(self, event_id, evt, include_discounts):
        price = evt["fields"]["Price (from Class)"][0]
        qty = evt["fields"]["Capacity (from Class)"][0]
        log.debug(f"{event_id} {evt['fields']['Name (from Class)']} {price} {qty}")
        neon.assign_pricing(
            event_id,
            price,
            qty,
            include_discounts=include_discounts,
            clear_existing=True,
        )

    @classmethod
    def _neon_category_from_event_name(cls, name):
        """Parses the event name and returns a category matching what kind of event it is"""
        if name == "All Member Meeting":
            return neon.Category.MEMBER_EVENT
        m = re.search(r"\w+? (\d+):", name)
        if m is None:
            return neon.Category.SOMETHING_ELSE_AMAZING
        if int(m[1]) >= 110:
            return neon.Category.PROJECT_BASED_WORKSHOP
        return neon.Category.SKILLS_AND_SAFETY_WORKSHOP

    def _schedule_event(  # pylint: disable=too-many-arguments
        self, event, desc, published=True, registration=True, dry_run=True
    ):
        start = dateparser.parse(event["fields"]["Start Time"]).astimezone(tz)
        end = start + datetime.timedelta(hours=event["fields"]["Hours (from Class)"][0])
        days = event["fields"]["Days (from Class)"][0]
        if days > 1:
            end += datetime.timedelta(days=days)
        name = event["fields"]["Name (from Class)"][0]
        capacity = event["fields"]["Capacity (from Class)"][0]
        return neon.create_event(
            name,
            desc,
            start,
            end,
            category=self._neon_category_from_event_name(name),
            max_attendees=capacity,
            dry_run=dry_run,
            published=published,
            registration=registration,
        )

    @lru_cache(maxsize=1)
    def _fetch_boilerplate(self):
        boilerplate = airtable.get_all_records("class_automation", "boilerplate")
        return [
            [b["fields"]["Notes"] for b in boilerplate if b["fields"]["Name"] == bname][
                0
            ]
            for bname in (
                "Rules & Expectations",
                "Cancellation Policy",
                "Age Requirement",
            )
        ]

    def _format_class_description(self, cls, suf=" (from Class)"):
        """Construct description of class from airtable columns; strip 'from Class' suffix"""
        (
            rules_and_expectations,
            cancellation_policy,
            age_section_fmt,
        ) = self._fetch_boilerplate()
        result = markdown.markdown(cls["fields"]["Short Description" + suf][0]) + "\n"
        sections = []
        for col in (
            "What you Will Create",
            "What to Bring/Wear",
            "Clearances Earned",
        ):
            body = cls["fields"].get(col + suf, [""])[0]
            if body.strip() != "":
                sections.append((col, body))

        if cls["fields"].get("Age Requirement" + suf) is not None:
            sections.append(
                (
                    "Age Requirement",
                    age_section_fmt.format(
                        age=cls["fields"]["Age Requirement" + suf][0]
                    ),
                )
            )

        result += "\n\n".join(
            [markdown.markdown(f"**{hdr}**\n\n{body}") for hdr, body in sections]
        )
        result += markdown.markdown(rules_and_expectations)
        result += markdown.markdown(cancellation_policy)
        return result

    def _resolve_schedule(self, min_future_days, overrides):
        now = tznow()
        for event in airtable.get_class_automation_schedule():
            cid = event["fields"]["ID"]
            start = dateparser.parse(event["fields"]["Start Time"]).astimezone(tz)
            if overrides:
                if str(cid) in overrides:
                    log.warning(f"Adding override class with ID {cid}")
                else:
                    continue  # Skip if not in override list
            else:
                if start < now:
                    log.debug(
                        f"Skipping event {cid} from the past {event['fields']['Name (from Class)']}"
                    )
                    continue
                # Quietly ignore already-scheduled events
                if event["fields"].get("Neon ID", "") != "":
                    log.debug(
                        f"Skipping scheduled event {cid} {event['fields']['Neon ID']}: "
                        f"{event['fields']['Name (from Class)']}"
                    )
                    continue

                if not event["fields"].get("Confirmed"):
                    log.debug(
                        f"Skipping unconfirmed: {start} {event['fields']['Name (from Class)'][0]} "
                        f"with {event['fields']['Instructor']}"
                    )
                    continue
                if start < now + datetime.timedelta(days=min_future_days):
                    log.debug(
                        f"Skipping too-soon: {start} {event['fields']['Name (from Class)'][0]} "
                        f"with {event['fields']['Instructor']}"
                    )
                    continue

            event["start"] = start
            event["cid"] = cid
            yield event

    @command(
        arg(
            "--min-future-days",
            help="Don't schedule classes closer than this many days",
            type=int,
            default=20,
        ),
        arg(
            "--apply",
            help="Actually push the classes; will only print otherwise",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--ovr",
            help="Only schedule items with this ID will always be acted upon (repeatable)",
            type=str,
            nargs="+",
            default=[],
        ),
        arg(
            "--publish",
            help="Publish the classes so they are visible in the event list",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
        arg(
            "--registration",
            help="Publish the classes so people can register to take them",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
        arg(
            "--discounts",
            help="Include AMP, Member, and Instructor discounts for all events",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
    )
    def post_classes_to_neon(
        self, args
    ):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        """Post a list of classes to Neon"""
        log.info(
            f"Classes will {'NOT ' if not args.publish else ''}be published to the public list"
        )
        log.info(
            f"Classes will {'NOT ' if not args.registration else ''}be open for registration"
        )
        num = 0
        to_schedule = list(self._resolve_schedule(args.min_future_days, args.ovr))
        scheduled_by_instructor = defaultdict(list)
        to_schedule.sort(key=lambda e: e["start"])
        to_reserve = {}
        log.info(f"Scheduling {len(to_schedule)} events:")
        for event in to_schedule:
            log.info(
                f"{event['start']} {event['cid']} {event['fields']['Instructor']}: "
                f"{event['fields']['Name (from Class)'][0]}"
            )
            scheduled_by_instructor[event["fields"]["Instructor"]].append(event)

            if args.apply:
                num += 1
                result_id = self._schedule_event(
                    event,
                    self._format_class_description(event),
                    dry_run=not args.apply,
                    published=args.publish,
                    registration=args.registration,
                )
                log.info(f"- Neon event {result_id} created")
                self._apply_pricing(result_id, event, args.discounts)
                log.info("- Pricing applied")
                airtable.update_record(
                    {"Neon ID": str(result_id)},
                    "class_automation",
                    "schedule",
                    event["id"],
                )
                log.info("- Neon ID updated in Airtable")
                to_reserve[event["cid"]] = reservation_dict_from_record(event)

        if num > 0:
            log.info("Reserving equipment for scheduled classes")
            self._reserve_equipment_for_class_internal(  # pylint: disable=no-member
                to_reserve, args.apply
            )

        print_yaml(builder.gen_class_scheduled_alerts(scheduled_by_instructor))
