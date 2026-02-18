"""Commands related to forwarding messages/applications from Asana and other locations"""

import argparse
import datetime
import logging
import re

from protohaven_api.automation.techs import techs as forecast
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import safe_parse_datetime, tznow
from protohaven_api.integrations import airtable, tasks
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.forwarding")


completion_re = re.compile("Deadline for Project Completion:\n(.*?)\n", re.MULTILINE)
description_re = re.compile("Project Description:\n(.*?)Materials Budget", re.MULTILINE)


class Commands:
    """Commands for managing classes"""

    @command(
        arg(
            "--apply",
            help="when true, Asana tasks are completed when comms are generated",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def project_requests(self, args, _):
        """Send alerts when new project requests fall into Asana"""
        if not args.apply:
            log.info(
                "\n***   --apply is not set, so projects will not be "
                + "checked off   ***\n"
            )
        num = 0
        results = []
        for req in tasks.get_project_requests():
            if req.get("completed"):
                continue
            req["notes"] = req["notes"].replace("\\n", "\n")
            deadline = completion_re.search(req["notes"])
            if deadline is None:
                raise RuntimeError(
                    "Failed to extract deadline from request by " + req["name"]
                )
            deadline = safe_parse_datetime(deadline[1])
            if deadline < tznow():
                log.info(
                    f"Skipping expired project request by {req['name']} (expired {deadline})"
                )
                continue

            results.append(
                Msg.tmpl(
                    "new_project_request", notes=req["notes"], target="#help-wanted"
                )
            )
            if args.apply:
                tasks.complete(req["gid"])
                log.info(f"marked complete: {req['gid']}")
            num += 1
        log.info(f"Done - {num} project request(s) generated")

        print_yaml(results)

    @command()
    def shop_tech_applications(self, _1, _2):
        """Send reminders to check shop tech applicants"""
        num = 0
        open_applicants = []
        for req in tasks.get_shop_tech_applicants(
            exclude_complete=True, exclude_on_hold=True
        ):
            open_applicants.append("- " + req["name"].split(",")[0])
            num += 1
        log.info(f"Found {num} open applications")
        log.info("\n".join(open_applicants))
        if num > 0:
            print_yaml(
                Msg.tmpl(
                    "shop_tech_applications",
                    num=len(open_applicants),
                    target="#tech-automation",
                )
            )
        else:
            print_yaml([])

    @command()
    def instructor_applications(self, _1, _2):
        """Send reminders to check for instructor applications"""
        num = 0
        open_applicants = []
        for req in tasks.get_instructor_applicants(
            exclude_on_hold=True, exclude_complete=True
        ):
            open_applicants.append("- " + req["name"].split(",")[0])
            num += 1
        log.info(f"Found {num} open instructor applications:")
        log.info("\n".join(open_applicants))

        if num > 0:
            print_yaml(
                Msg.tmpl(
                    "instructor_applications",
                    num=len(open_applicants),
                    target="#edu-automation",
                )
            )
        else:
            print_yaml([])

    @command()
    def donation_requests(self, _1, _2):
        """Send reminders to triage donation requests"""
        num = 0
        open_requests = []
        for req in tasks.get_donation_requests(exclude_complete=True):
            open_requests.append("- " + req["name"].split(",")[0])
            num += 1
        log.info(f"Found {num} open donation requests:")
        log.info("\n".join(open_requests))
        if num > 0:
            print_yaml(
                Msg.tmpl(
                    "donation_requests",
                    num=len(open_requests),
                    requests=open_requests,
                    target="#donation-automation",
                )
            )
        else:
            print_yaml([])

    @command()
    def supply_requests(self, _1, _2):
        """Send reminders to purchase requested instructor supplies"""
        num = 0
        reqs = []
        now = tznow()
        for c in airtable.get_class_automation_schedule():
            d = safe_parse_datetime(c["fields"]["Start Time"])
            if d < now or c["fields"]["Supply State"] != "Supplies Requested":
                continue

            reqs.append(
                {
                    "days": (d - now).days,
                    "name": ", ".join(c["fields"]["Name (from Class)"]),
                    "date": d.strftime("%Y-%m-%d"),
                    "inst": c["fields"]["Instructor"],
                }
            )
            log.info(str(reqs[-1]))
            num += 1
        if num > 0:
            print_yaml(
                Msg.tmpl(
                    "class_supply_requests",
                    num=len(reqs),
                    requests=reqs,
                    target="#supply-automation",
                )
            )
        else:
            print_yaml([])

    def _form_from_task_notes(self, notes):
        """Extract Asana form data from the Notes field of the task"""
        field = None
        body = []
        result = {}
        for line in notes.split("\n"):
            line = line.strip()
            if line.startswith("——————"):
                break
            if line.endswith(":"):
                if field is not None:
                    result[field] = "\n".join(body)
                    body = []
                field = line[:-1]
                continue
            body.append(line)
        if field is not None:
            result[field] = "\n".join(body)
        return result

    def _format_private_instruction_request_task(self, req, now, summary_limit):
        """Return a string summary of the private instruction request"""
        d = safe_parse_datetime(req["created_at"])
        dt = now - d
        form = self._form_from_task_notes(req["notes"])
        summary = form["Details"].replace("\n", " ")
        if len(summary) > summary_limit:
            summary = summary[: summary_limit - 3] + "..."

        ddur = dt.days
        if ddur > 7:
            duration = f"{ddur//7} weeks"
        else:
            duration = f"{ddur} days"

        avail = form["Availability"].replace("\n", ", ")
        if len(avail) > summary_limit / 2:
            avail = avail[: int(summary_limit / 2 - 3)] + "..."
        fmt = (
            f"- {d.strftime('%b %-d'):6} {'(' + duration + ' ago)':14} "
            f"{form['Name'].strip()}, {form['Email'].strip()}: "
            f"{summary} (Availability: {avail})"
        )
        return dt, fmt

    @command(
        arg(
            "--daily",
            help="when true, daily reminder info is sent and weekly summaries suppressed",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--summary_limit",
            help="Max character length of instruction request summaries sent to Discord",
            type=int,
            default=300,
        ),
    )
    def private_instruction(self, args, _):  # pylint: disable=
        """Generate reminders to take action on private instruction.
        This targets membership@ email and Discord's #instructors/#edu-automation channels
        """
        formatted = []
        formatted_past_day = []
        num = 0
        now = tznow()
        for req in tasks.get_private_instruction_requests():
            if req.get("completed"):
                continue
            dt, fmt = self._format_private_instruction_request_task(
                req, now, args.summary_limit
            )
            formatted.append(fmt)
            if dt.days < 1 and dt.seconds // 3600 < 24:
                formatted_past_day.append(fmt)
            num += 1

        log.info(
            f"Found {num} open private instruction requests "
            f"({len(formatted_past_day)} in the past day)"
        )

        results = []
        if not args.daily and len(formatted) > 0:
            log.info("Generating weekly summaries")
            results.append(
                Msg.tmpl(
                    "instruction_requests",
                    num=len(formatted),
                    formatted=formatted[:5],
                    target="membership@protohaven.org",
                )
            )
            results.append(
                Msg.tmpl(
                    "instruction_requests",
                    num=len(formatted),
                    formatted=formatted[:5],
                    target="#edu-automation",
                )
            )
        if args.daily and len(formatted_past_day) > 0:
            log.info("Generating daily request to instructors")
            results.append(
                Msg.tmpl(
                    "daily_private_instruction",
                    formatted=formatted_past_day[:5],
                    target="#private-instructors",
                )
            )
        print_yaml(results)

    @command(
        arg(
            "--apply",
            help="when true, Asana tasks are completed when comms are generated",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def phone_messages(self, args, _):
        """Check on phone messages and forward to email"""
        if not args.apply:
            log.info(
                "\n***   --apply is not set, so tasks will not be "
                + "checked off   ***\n"
            )
        num = 0
        results = []
        for req in tasks.get_phone_messages():
            if req.get("completed"):
                continue
            results.append(
                Msg.tmpl(
                    "phone_message",
                    target="hello@protohaven.org",
                    msg_header=req["name"].split(",")[0],
                    date=safe_parse_datetime(req["created_at"]),
                    notes=req["notes"],
                )
            )
            if args.apply:
                tasks.complete(req["gid"])
                log.info(f"marked complete: {req['gid']}")
            num += 1
        log.info(f"Found {num} open phone messages")

        print_yaml(results)

    def _cur_shift(self, now):
        if now.hour < 10:  # Earlier than start of shift, so prev shift
            return f"{(now - datetime.timedelta(days=1)).strftime('%A')} PM"
        return f"{now.strftime('%A')} {'AM' if now.hour < 16 else 'PM'}"

    @command(
        arg("--now", help="Override current time", type=str, default=None),
    )
    def tech_sign_ins(self, args, _):
        """Craft a notification to indicate whether the scheduled techs have signed in
        for their shift"""
        now = tznow() if not args.now else safe_parse_datetime(args.now)
        shift = self._cur_shift(now)
        start = now.replace(hour=8)
        end = now.replace(hour=11 if now.hour < 16 else 17)
        log.info(
            f"Checking sign-ins, current time {now}, shift {shift}, range {start} - {end}"
        )

        # Current day from calendar
        techs_on_duty_day = forecast.generate(now, 1, include_pii=True)[
            "calendar_view"
        ][0]
        # Pick AM vs PM shift
        techs_on_duty = techs_on_duty_day["AM" if shift.endswith("AM") else "PM"][
            "people"
        ]

        # Short if no techs are on duty and today is a holidy.  Overridden
        # holiday shifts will have techs_on_duty populated, so we shouldn't
        # need further checks here. See: `create_calendar_view` in `techs`
        if len(techs_on_duty) == 0 and techs_on_duty_day["is_holiday"]:
            log.info("Oh, it's a holiday, shop's closed.")
            print_yaml([])
            return

        log.info(f"Expecting on-duty techs: {[t.name for t in techs_on_duty]}")
        email_map = {}
        for t in techs_on_duty:
            for email in t.emails:
                if email in email_map:
                    error_msg = (
                        'Collision detected: email "{email}" in '
                        "member {t} AND member {member}. "
                        "Ignoring {t}."
                    ).format(email=email, t=t, member=email_map[email])
                    log.warning(error_msg)
                else:
                    email_map[email] = t
        on_duty_ok = False
        for s in list(airtable.get_signins_between(start, end)):
            if s is None:
                continue
            t = email_map.get(s.email)
            if t in techs_on_duty:
                on_duty_ok = True
                timestamp = s.created or now
                log.info(
                    f"{t.name} ({s.email}, signed in {timestamp.strftime('%-I%p')})"
                )
            else:
                log.info(s.email)

        result = []
        if not on_duty_ok:
            result.append(
                Msg.tmpl(
                    "shift_no_techs",
                    target="#tech-automation",
                    shift=shift,
                    onduty=techs_on_duty,
                )
            )

        print_yaml(result)
