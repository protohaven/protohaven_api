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
    eventbrite,
    neon_base,
)
from protohaven_api.integrations.comms import Msg
from protohaven_api.integrations.data.neon import Category

log = logging.getLogger("cli.classes")


def resolve_schedule(min_future_days, overrides):
    """Resolves class schedule, excluding ones not relevant"""
    now = tznow()
    for event in airtable.get_class_automation_schedule(raw=False):
        if overrides:
            if str(event.schedule_id) in overrides:
                log.warning(
                    f"Adding override class with schedule ID {event.schedule_id}"
                )
            else:
                continue  # Skip if not in override list
        else:
            if event.start_time < now:
                log.info(
                    f"Skipping event {event.schedule_id} from the past {event.name}"
                )
                continue

            if (event.neon_id or "") != "":
                log.info(
                    f"Skipping scheduled event {event.schedule_id} {event.neon_id}: "
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
        arg(
            "--require_teachable",
            help="Only send reminders to instructors with teachable classes",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
    )
    def gen_instructor_schedule_reminder(self, args, _):
        """Reads the list of instructors from Airtable and generates
        reminder comms to all instructors, plus the #instructors discord,
        to propose additional class scheduling times"""

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
        for nid, email in builder.get_unscheduled_instructors(
            start,
            end,
            require_active=args.require_active,
            require_teachable=args.require_teachable,
        ):
            if filt and nid not in filt and email not in filt:
                continue
            m = neon_base.fetch_account(nid)
            results.append(
                Msg.tmpl(
                    "instructor_schedule_classes",
                    firstname=m.fname,
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

        if cls.description.get("Age Requirement") is not None:
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

    @classmethod
    def reserve_equipment_for_event(cls, event, apply):
        """Reserves equipment for a class"""
        # Convert areas to booked IDs using tool table
        areas = set(event.areas)
        log.info(f"Resolving equipment from event areas: {areas}")
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
        arg(
            "--use-eventbrite",
            help="Post class to eventbrite instead of to Neon CRM",
            action=argparse.BooleanOptionalAction,
            default=False,
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
        log.info(
            f"Discounts will {'NOT ' if not args.discounts else ''}be applied to new classes"
        )
        log.info(
            f"Equipment will {'NOT ' if not args.reserve else ''}be reserved for new classes"
        )
        log.info(
            f"{'Eventbrite' if args.use_eventbrite else 'Neon'} will host the event"
        )
        if args.ovr:
            log.info(
                "Overriding to specifically schedule ONLY classes in Airtable "
                f"Schedule with ID {args.ovr}"
            )

        num = 0
        to_schedule: list[airtable.Class] = list(
            resolve_schedule(args.min_future_days, args.ovr)
        )
        scheduled_by_instructor = defaultdict(list)
        to_schedule.sort(key=lambda e: e.start_time)

        log.info("Attempting auth as user to allow for pricing changes")
        session = None if args.use_eventbrite else neon_base.NeonOne()

        log.info(f"Scheduling {len(to_schedule)} events:")
        for event in to_schedule:
            log.info(
                f"{event.start_time} {event.schedule_id} {event.instructor_name}: {event.name}"
            )
            log.info(
                f"${event.price}, {event.capacity} students, sessions "
                f"{[s[0].strftime('%Y-%m-%d %-I:%M %p') for s in event.sessions]}"
            )

            num += 1
            result_id = None
            try:
                if args.apply and not args.use_eventbrite:
                    result_id = neon_base.create_event(
                        event.name,
                        desc=self._format_class_description(event),
                        start=event.sessions[0][0],
                        end=event.sessions[-1][1],
                        category=self._neon_category_from_event_name(event.name),
                        max_attendees=event.capacity,
                        dry_run=not args.apply,
                        published=args.publish,
                        registration=args.registration,
                    )
                elif args.apply and args.use_eventbrite:
                    image_id = None
                    if event.image_link:
                        log.info(
                            f"- Pushing image URL to Eventbrite: {event.image_link}"
                        )
                        image_id = eventbrite.upload_logo_image(event.image_link)
                        log.info(f"- Logo image ID: {image_id}")

                    result_id = eventbrite.create_event(
                        event.name,
                        event.sessions,
                        max_attendees=event.capacity,
                        published=args.publish,
                        logo_id=image_id,
                    )
                else:
                    result_id = "DRYRUN"
                log.info(f"- Event #{result_id} created")
                assert result_id
                event.neon_id = str(result_id)

                if args.apply and args.use_eventbrite:
                    desc = self._format_class_description(event)
                    content_version = eventbrite.set_structured_content(
                        event.neon_id, desc
                    )
                    log.info(
                        f"  Structured content added for {event.neon_id}: {content_version}"
                    )

                log.info("- Assigning pricing")
                if args.apply and not args.use_eventbrite:
                    log.info("  (uses Firefox process via playwright)")
                    session.assign_pricing(
                        event.neon_id,
                        event.price,
                        event.capacity,
                        include_discounts=args.discounts,
                        clear_existing=True,
                    )
                    log.info("  Pricing assigned")
                elif args.apply and args.use_eventbrite:
                    log.info(
                        str(
                            eventbrite.assign_pricing(
                                event.neon_id,
                                event.price,
                                event.capacity,
                                clear_existing=True,
                            )
                        )
                    )
                    log.info("  Pricing assigned; publishing event")
                    pub_rep = eventbrite.set_event_scheduled_state(
                        event.neon_id, scheduled=args.registration
                    )
                    log.info(f"  {pub_rep}")
                    log.info(f"  Eventbrite event published: {event.neon_id}")

                else:
                    log.info("  Skip (--no-apply)")

                if args.apply:
                    airtable.update_record(
                        {"Neon ID": event.neon_id},
                        "class_automation",
                        "schedule",
                        event.schedule_id,
                    )
                    log.info("- Neon ID updated in Airtable")
                else:
                    log.info(
                        f"  Skipped Neon ID update in airtable ({event.schedule_id})"
                    )

                if args.reserve:
                    log.info("Reserving equipment for scheduled classes")
                    self.reserve_equipment_for_event(event, args.apply)

                scheduled_by_instructor[event.instructor_email].append(event)
                log.info("Added to notification list")
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.error(f"Failed to create event #{result_id}: {str(e)[:256]}...")
                log.error(traceback.format_exc())
                if result_id:
                    log.error("Failed; reverting event creation")
                    if args.use_eventbrite:
                        log.info(eventbrite.delete_event_unsafe(result_id))
                    else:
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
