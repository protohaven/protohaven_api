"""Commands related to forwarding messages/applications from Asana and other locations"""
import argparse
import logging
import re
from datetime import datetime

import yaml
from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import tz, tznow  # pylint: disable=import-error
from protohaven_api.integrations import (  # pylint: disable=import-error
    airtable,
    neon,
    sheets,
    tasks,
)

log = logging.getLogger("cli.forwarding")


completion_re = re.compile("Deadline for Project Completion:\n(.*?)\n", re.MULTILINE)
description_re = re.compile("Project Description:\n(.*?)Materials Budget", re.MULTILINE)


class Commands:
    """Commands for managing classes in Airtable and Neon"""

    @command(
        arg(
            "--apply",
            help="when true, Asana tasks are completed when comms are generated",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def project_requests(self, args):
        """Send alerts when new project requests fall into Asana"""
        if not args.apply:
            log.info(
                "\n***   --apply is not set, so projects will not be "
                + "checked off   ***\n"
            )
        num = 0
        results = []
        for req in tasks.get_project_requests():
            if req["completed"]:
                continue
            req["notes"] = req["notes"].replace("\\n", "\n")
            deadline = completion_re.search(req["notes"])
            if deadline is None:
                raise RuntimeError(
                    "Failed to extract deadline from request by " + req["name"]
                )
            deadline = dateparser.parse(deadline[1]).astimezone(tz)
            if deadline < tznow():
                log.info(
                    f"Skipping expired project request by {req['name']} (expired {deadline})"
                )
                continue

            results.append(
                {
                    "id": "",
                    "target": "#help-wanted",
                    "subject": "**New Project Request:**",
                    "body": req["notes"],
                }
            )
            if args.apply:
                tasks.complete(req["gid"])
                log.info(f"marked complete: {req['gid']}")
            num += 1
        log.info(f"Done - {num} project request(s) generated")

        print(yaml.dump(results, default_flow_style=False, default_style=""))

    @command()
    def shop_tech_applications(self, _):
        """Send reminders to check shop tech applicants"""
        num = 0
        open_applicants = []
        for req in tasks.get_shop_tech_applicants():
            if req["completed"]:
                continue
            open_applicants.append("- " + req["name"].split(",")[0])
            num += 1
        log.info(f"Found {num} open applications")

        if num > 0:
            body = "The following applicants are waiting for a decision:\n"
            body += "\n".join(open_applicants)
            body += "\nDetails at https://app.asana.com/0/1203664351777333"

            result = {
                "id": "",
                "target": "#tech-leads",
                "subject": "**Open shop tech applications:**",
                "body": body,
            }
            print(yaml.dump([result], default_flow_style=False, default_style=""))

    @command()
    def instructor_applications(self, _):
        """Send reminders to check for instructor applications"""
        num = 0
        open_applicants = []
        for req in tasks.get_instructor_applicants():
            if req["completed"]:
                continue
            open_applicants.append("- " + req["name"].split(",")[0])
            num += 1
        log.info(f"Found {num} open instructor applications")

        if num > 0:
            log.info("Generating summary email")
            body = "The following applicants are waiting for a decision:\n"
            body += "\n".join(open_applicants)
            body += "\nDetails at https://app.asana.com/0/1202211433878591"

            result = {
                "id": "",
                "target": "#education-leads",
                "subject": "**Open instructor applications:**",
                "body": body,
            }
            print(yaml.dump([result], default_flow_style=False, default_style=""))

    @command()
    def class_proposals(self, _):
        """Send reminders to take action on proposed classes"""
        num = 0
        unapproved_classes = []
        for r in airtable.get_all_class_templates():
            if r["fields"].get("Approved") is not None:
                continue
            unapproved_classes.append("- " + r["fields"]["Name"])
            num += 1
        log.info(f"Found {num} proposed classes awaiting approval.")

        if num > 0:
            body = "The following classes are proposed, but not yet approved for scheduling:\n"
            body += "\n".join(unapproved_classes)
            body += "\nDetails at https://airtable.com/applultHGJxHNg69H/tblBHGwrU8cwVwbHI/ "
            body += "(requires Airtable credentials)"

            result = {
                "id": "",
                "target": "#education-leads",
                "subject": "**Proposed classes awaiting approval:**",
                "body": body,
            }
            print(yaml.dump([result], default_flow_style=False, default_style=""))

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

    def _format_private_instruction_request_task(self, req, now):
        """Return a string summary of the private instruction request"""
        d = dateparser.parse(req["created_at"]).astimezone(tz)
        dt = now - d
        form = self._form_from_task_notes(req["notes"])
        summary = form["Details"].replace("\n", " ")
        if len(summary) > 120:
            summary = summary[:117] + "..."

        ddur = dt.days
        if ddur > 7:
            duration = f"{ddur//7} weeks"
        else:
            duration = f"{ddur} days"

        avail = form["Availability"].replace("\n", ", ")
        if len(avail) > 90:
            avail = avail[:87] + "..."
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
    )
    def private_instruction(self, args):  # pylint: disable=
        """Generate reminders to take action on private instruction.
        This targets membership@ email and Discord's #instructors/#education-leads channels
        """
        formatted = []
        formatted_past_day = []
        num = 0
        now = tznow()
        for req in tasks.get_private_instruction_requests():
            if req["completed"]:
                continue
            dt, fmt = self._format_private_instruction_request_task(req, now)
            formatted.append(fmt)
            if dt.days < 1 and dt.seconds // 3600 < 24:
                formatted_past_day.append(fmt)
            num += 1

        log.info(f"Found {num} open private instruction requests")

        results = []
        if not args.daily and len(formatted) > 0:
            log.info("Generating weekly summaries")
            results.append(
                {
                    "id": "",
                    "target": "membership@protohaven.org",
                    "subject": f"{num} Private Instruction Request(s) Active",
                    "body": (
                        "The following requests are active for private instruction:\n\n"
                        + "\n".join(formatted)
                        + "\n\nPlease go to "
                        + "https://app.asana.com/0/1203922725251220/1207896962249498 "
                        + "and check off any requests that have already been handled, and raise "
                        + "the rest to the instructors to fulfill."
                    ),
                }
            )
            results.append(
                {
                    "id": "",
                    "target": "#education-leads",
                    "subject": f"{num} Private Instruction Request(s) Active",
                    "body": (
                        "The following requests are active for private instruction "
                        + f"(showing up to 5 most recent, of {num}):\n\n"
                        + "\n".join(formatted[:5])
                        + "\n\nPlease go to "
                        + "https://app.asana.com/0/1203922725251220/1207896962249498 and check off "
                        + "any requests that have already been handled, and raise the rest "
                        + "to the instructors to fulfill."
                    ),
                }
            )
        if args.daily and len(formatted_past_day) > 0:
            log.info("Generating daily request to instructors")
            results.append(
                {
                    "id": "",
                    "target": "#instructors",
                    "subject": "New Private Instruction Request(s) in the past 24 hours",
                    "body": (
                        "\n".join(formatted_past_day)
                        + "\n\nPlease go to "
                        + "https://app.asana.com/0/1203922725251220/1207896962249498 and assign "
                        + "yourself if you'd like to take any requests. If you lack access, ask "
                        + "one of the staff or education leads. Thanks!"
                    ),
                }
            )
        print(yaml.dump(results, default_flow_style=False, default_style=""))

    @command(
        arg(
            "--apply",
            help="when true, Asana tasks are completed when comms are generated",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def phone_messages(self, args):
        """Send reminders to check shop tech applicants"""
        num = 0
        results = []
        for req in tasks.get_phone_messages():
            if req["completed"]:
                continue
            d = dateparser.parse(req["created_at"]).strftime("%B %-d")
            results.append(
                {
                    "id": "",
                    "target": "hello@protohaven.org",
                    "subject": f"New phone message: {req['name'].split(',')[0]} ({d})",
                    "body": req["notes"]
                    + "\nDetails at https://app.asana.com/0/1203963688927297/1205117134611637",
                }
            )
            if args.apply:
                tasks.complete(req["gid"])
                log.info(f"marked complete: {req['gid']}")
            num += 1
        log.info(f"Found {num} open phone messages")

        print(yaml.dump(results, default_flow_style=False, default_style=""))

    def _cur_shift(self, now):
        if now.hour < 10:  # Earlier than start of shift, so prev shift
            return f"{now - datetime.timedelta(days=1).strftime('%A')} PM"
        return f"{now.strftime('%A')} {'AM' if now.hour < 16 else 'PM'}"

    @command(arg("--now", help="Override current time", type=str, default=None))
    def tech_sign_ins(self, args):
        """Craft a notification to indicate whether the scheduled techs have signed in
        for their shift"""
        now = tznow() if not args.now else dateparser.parse(args.now).astimezone(tz)
        shift = self._cur_shift(now)
        start = now.replace(hour=8)
        end = now.replace(hour=11 if now.hour < 16 else 17)
        log.info(
            f"Checking sign-ins, current time {now}, shift {shift}, range {start} - {end}"
        )

        result = []
        techs_on_duty = {
            t["email"]: t["name"]
            for t in neon.fetch_techs_list()
            if t["shift"] == shift
        }
        log.info(f"Expecting on-duty techs: {techs_on_duty}")

        for s in list(sheets.get_sign_ins_between(start, end)):
            email = s[
                "Email address (members must use the address from your Neon Protohaven account)"
            ].lower()
            log.debug(f"- {email}")
            tod = techs_on_duty.get(email)
            if tod:
                result.append(
                    f"{tod} ({email}, signed in {s['Timestamp'].strftime('%-I%p')})"
                )

        print(
            yaml.dump(
                [
                    {
                        "id": "",
                        "target": "#techs-live",
                        "subject": f"Staffing report for {shift} shift",
                        "body": (
                            (
                                "No techs assigned this shift have signed in."
                                if len(result) == 0
                                else "\n".join(result)
                            )
                            + "\nSee who's scheduled at https://api.protohaven.org/techs"
                        ),
                    }
                ]
            )
        )
