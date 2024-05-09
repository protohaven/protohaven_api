"""Commands related to forwarding messages/applications from Asana and other locations"""
import argparse
import logging
import re

import yaml
from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import tz, tznow  # pylint: disable=import-error
from protohaven_api.integrations import comms, tasks  # pylint: disable=import-error

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
    def shop_tech_applications(self, args):
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
