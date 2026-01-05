"""Commands related to classes in Neon and Airtable"""

import argparse
import datetime
import logging
import re
import traceback
from collections import defaultdict
from functools import lru_cache

import markdown

from protohaven_api.automation.classes import builder
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import (  # pylint: disable=import-error
    safe_parse_datetime,
    tznow,
)
from protohaven_api.integrations import (  # pylint: disable=import-error
    airtable,
    booked,
    comms,
    neon_base,
)
from protohaven_api.integrations.comms import Msg
from protohaven_api.integrations.data.neon import Category

log = logging.getLogger("cli.classes")


def resolve_schedule(min_future_days, overrides):
    now = tznow()
    for event in airtable.get_class_automation_schedule(raw=False):
        if overrides:
            if str(event.class_id) in overrides:
                log.warning(f"Adding override class with ID {event.class_id}")
            else:
                continue  # Skip if not in override list
        else:
            if event.start_time < now:
                log.info(f"Skipping event {event.class_id} from the past {event.name}")
                continue
            # Quietly ignore already-scheduled events
            if (event.neon_id or "") != "":
                log.info(
                    f"Skipping scheduled event {event.class_id} {event.neon_id}: "
                    f"{event.name}"
                )
                continue

            if not event.confirmed:
                log.info(
                    f"Skipping unconfirmed: {event.start_time} {event.name} "
                    f"with {event.instructor_name}"
                )
                continue
            if event.start_time < now + datetime.timedelta(days=min_future_days):
                log.info(
                    f"Skipping too-soon: {event.start_time} {event.name} "
                    f"with {event.instructor_name}"
                )
                continue
        yield event


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
        arg(
            "--filter",
            help="CSV of instructor names/emails to restrict to; all others will be skipped",
            type=str,
            default=None,
        ),
        arg(
            "--require_active",
            help="Only send reminders to active instructors (checkbox in Airtable)",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
    )
    def gen_instructor_schedule_reminder(self, args, _):
        """Reads the list of instructors from Airtable and generates
        reminder comms to all instructors, plus the #instructors discord,
        to propose additional class scheduling times"""

        log.info("Hello world")

        start = (
            safe_parse_datetime(args.start)
            if args.start
            else tznow() + datetime.timedelta(days=30)
        )
        end = (
            safe_parse_datetime(args.end)
            if args.end
            else start + datetime.timedelta(days=30)
        )
        results = []
        summary = {"name": "Scheduling reminder", "action": ["SEND"], "targets": set()}
        filt = [f.strip() for f in args.filter.split(",")] if args.filter else None
        for name, email in builder.get_unscheduled_instructors(
            start, end, require_active=args.require_active
        ):
            if filt and name not in filt and email not in filt:
                continue
            results.append(
                Msg.tmpl(
                    "instructor_schedule_classes",
                    name=name,
                    firstname=name.split(" ")[0],
                    start=start,
                    end=end,
                    target=email,
                )
            )
            summary["targets"].add(email)

        if len(results) > 0:
            results.append(
                Msg.tmpl(
                    "class_automation_summary",
                    events={"": summary},
                    target="#class-automation",
                )
            )
        print_yaml(results)
        log.info(f"Generated {len(results)} notification(s)")

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
        arg(
            "--published_only",
            help="Only consider published classes when building emails",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
        arg(
            "--cache",
            help="Deprecated; no longer used but included to prevent breakage",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
    )
    def gen_class_emails(self, args, _):
        """Reads schedule of classes from Neon and Airtable and outputs
        a list of emails to send to instructors, techs, and students.
        This does not actually send the emails; for that, see send_comms."""
        b = builder.ClassEmailBuilder(logging.getLogger("cli.email_builder"))
        b.ignore_ovr = args.ignore or []
        b.cancel_ovr = args.cancel or []
        b.confirm_ovr = args.confirm or []
        b.filter_ovr = args.filter or []
        b.published = args.published_only
        log.info(
            f"Configured email builder: ignore_ovr {b.ignore_ovr} cancel_ovr {b.cancel_ovr} "
            f"confirm_ovr {b.confirm_ovr} filter_ovr {b.filter_ovr} published_only {b.published}"
        )
        result = b.build()
        print_yaml(result)
        log.info(f"Generated {len(result)} notification(s)")

    def _apply_pricing(self, event_id, evt, include_discounts, session):
        log.debug(f"{event_id} {evt.name} {evt.price} {evt.capacity}")
        session.assign_pricing(
            event_id,
            evt.price,
            evt.capacity,
            include_discounts=include_discounts,
            clear_existing=True,
        )

    @classmethod
    def _neon_category_from_event_name(cls, name):
        """Parses the event name and returns a category matching what kind of event it is"""
        if name == "All Member Meeting":
            return Category.MEMBER_EVENT
        m = re.search(r"\w+? (\d+):", name)
        if m is None:
            return Category.SOMETHING_ELSE_AMAZING
        if int(m[1]) >= 110:
            return Category.PROJECT_BASED_WORKSHOP
        return Category.SKILLS_AND_SAFETY_WORKSHOP

    def _schedule_event(  # pylint: disable=too-many-arguments
        self, event, desc, published=True, registration=True, dry_run=True
    ):
        dates = [safe_parse_datetime(s) for s in event["fields"]["Sessions"].split(",")]
        name = event["fields"]["Name (from Class)"][0]
        capacity = event["fields"]["Capacity (from Class)"][0]
        return neon_base.create_event(
            name,
            desc,
            dates[0][0],
            dates[-1][1],
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

    def _format_class_sessions(self, cls):
        """Format the dates and times for an airtable class"""
        lines = []
        for d0, d1 in cls.sessions:
            lines.append(f"{d0.strftime('%A %b %-d, %-I%p')} - {d1.strftime('%-I%p')}")
        result = "**Class Dates**\n\n"
        result += "\n".join([f"* {l}" for l in lines])
        return result

    def _format_class_description(self, cls):
        """Construct description of class from airtable columns; strip 'from Class' suffix"""
        (
            rules_and_expectations,
            cancellation_policy,
            age_section_fmt,
        ) = self._fetch_boilerplate()
        result = ""
        if cls.image_link:
            result += f'<p><img height="200" src="{cls.image_link}"/></p>\n'
        result += markdown.markdown(cls.description["Short Description"]) + "\n"
        sections = []
        for col in (
            "What you Will Create",
            "What to Bring/Wear",
            "Clearances Earned",
        ):
            body = cls.description[col]
            if body is not None and body.strip() != "":
                sections.append((col, body))

        if cls["description"].get("Age Requirement") is not None:
            sections.append(
                (
                    "Age Requirement",
                    age_section_fmt.format(
                        age=cls.description["Age Requirement"],
                    ),
                )
            )

        result += "\n\n".join(
            [markdown.markdown(f"**{hdr}**\n\n{body}") for hdr, body in sections]
        )
        result += markdown.markdown(self._format_class_sessions(cls))
        result += markdown.markdown(rules_and_expectations)
        result += markdown.markdown(cancellation_policy)
        return result

    def _reserve_equipment_for_event(self, event, apply):
        """Reserves equipment for a class"""
        # Convert areas to booked IDs using tool table
        areas = set(event.areas)
        resources = []
        for row in airtable.get_all_records("tools_and_equipment", "tools"):
            for a in row["fields"].get("Name (from Shop Area)", []):
                if a in areas and row["fields"].get("BookedResourceId"):
                    resources.append(
                        (
                            row["fields"]["Tool Name"],
                            row["fields"]["BookedResourceId"],
                        )
                    )
                    break

        log.info(f"Class {event.name} has {len(resources)} resources:")
        for name, resource_id in resources:
            for start, end in event.sessions:
                log.info(
                    f"  Reserving {name} (Booked ID {resource_id}) from "
                    f"{start} to {end} (apply={apply})"
                )
                if apply:
                    log.info(
                        str(
                            booked.reserve_resource(
                                resource_id, start, end, title=event.name
                            )
                        )
                    )

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
            "--reserve",
            help="Pre-reserve equipment in the areas when the class is sheduled",
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
        self, args, _
    ):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        """Post a list of classes to Neon"""
        log.info(
            f"Classes will {'NOT ' if not args.publish else ''}be published to the public list"
        )
        log.info(
            f"Classes will {'NOT ' if not args.registration else ''}be open for registration"
        )
        num = 0
        to_schedule: list[airtable.Class] = list(
            self.resolve_schedule(args.min_future_days, args.ovr)
        )
        scheduled_by_instructor = defaultdict(list)
        to_schedule.sort(key=lambda e: e.start_time)

        log.info("Attempting auth as user to allow for pricing changes")
        session = neon_base.NeonOne()

        log.info(f"Scheduling {len(to_schedule)} events:")
        for event in to_schedule:
            log.info(
                f"{event.start_date} {event.class_id} {event.instructor_name}: {event.name}"
            )

            if args.apply:
                num += 1
                result_id = None
                try:
                    result_id = self._schedule_event(
                        event,
                        self._format_class_description(event),
                        dry_run=not args.apply,
                        published=args.publish,
                        registration=args.registration,
                    )
                    log.info(f"- Neon event {result_id} created")
                    assert result_id
                    event.neon_id = str(result_id)

                    log.info("- Applying pricing (uses Firefox process via playwright)")
                    self._apply_pricing(result_id, event, args.discounts, session)
                    log.info("- Pricing applied")

                    airtable.update_record(
                        {"Neon ID": event.neon_id},
                        "class_automation",
                        "schedule",
                        event.schedule_id,
                    )
                    log.info("- Neon ID updated in Airtable")

                    if args.reserve:
                        log.info("Reserving equipment for scheduled classes")
                        self._reserve_equipment_for_event(event, args.apply)

                    scheduled_by_instructor[event.instructor_id].append(event)
                    log.info("Added to notification list")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.error(f"Failed to create event #{result_id}: {str(e)[:256]}...")
                    log.error(traceback.format_exc())
                    if result_id:
                        log.error("Failed; reverting event creation")
                        log.info(neon_base.delete_event_unsafe(result_id))
                        airtable.update_record(
                            {"Neon ID": ""},
                            "class_automation",
                            "schedule",
                            event.schedule_id,
                        )
                    try:
                        comms.send_discord_message(
                            f"Reverted class #{result_id}; creation failed: {str(e)[:256]}...\n"
                            "Check Cronicle logs for details",
                            "#class-automation",
                            blocking=False,
                        )
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

        print_yaml(builder.gen_class_scheduled_alerts(scheduled_by_instructor))
