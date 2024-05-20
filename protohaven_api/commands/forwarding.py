"""Commands related to forwarding messages/applications from Asana and other locations"""
import argparse
import logging
import re

import yaml
from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import tz, tznow  # pylint: disable=import-error
from protohaven_api.integrations import (  # pylint: disable=import-error
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
