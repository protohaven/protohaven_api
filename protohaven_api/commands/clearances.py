"""Commands related operations on Dicsord"""

import argparse
import datetime
import logging

from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tz, tznow
from protohaven_api.integrations import sheets
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.roles")

PASS_HDR = "Protohaven emails of each student who PASSED (This should be the email address they used to sign up for the class or for their Protohaven account). If none of them passed, enter N/A."
CLEARANCE_HDR = "Which clearance(s) was covered?"
TOOLS_HDR = "Which tools?"


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for managing roles of members"""

    @command(
        arg(
            "--apply",
            help="when true, Neon is updated with clearances",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--filter_users",
            help="Restrict to comma separated list of email addresses",
            type=str,
        ),
        arg(
            "--filter_clearances",
            help="Restrict to comma separated list of clearances",
            type=str,
        ),
        arg(
            "--after",
            help="Don't process this comma separated list of discord users",
            type=str,
        ),
        arg(
            "--max_users_affected",
            help="Only allow at most this number of users to receive clearance changes",
            type=int,
            default=5,
        ),
    )
    def sync_clearances(self, args, _):  # pylint: disable=too-many-locals
        """Fetchesclearances in the Master Instructor Hours and Clearance Log,
        expands them to individual tool codes, and updates accounts in Neon CRM with
        assigned clearances.

        This is a "backfill" equivalent to the AppScript automation that runs on form
        submission.
        """
        if not args.apply:
            log.warning(
                "***** --apply not set; clearances will not actually change *****"
            )
        log.info("Fetching role intents from Neon and Discord")
        user_filter = set(args.filter_users.split(",")) if args.filter_users else None
        clearance_filter = (
            set(args.filter_clearances.split(",")) if args.filter_clearances else None
        )
        dt = (
            tznow() - datetime.timedelta(days=30)
            if not args.after
            else dateparser.parse(args.after)
        )
        changes = {}

        all_codes = neon.fetch_clearance_codes()
        name_to_code = {c["name"]: c["code"] for c in all_codes}
        code_to_id = {c["code"]: c["id"] for c in all_codes}

        for sub in sheets.get_instructor_submissions():
            if sub["Timestamp"].astimezone(tz) < dt:
                continue
            log.info(sub)
            emails = sub.get(PASS_HDR)
            clearance_codes = sub.get(CLEARANCE_HDR)
            clearance_codes = (
                [s.split(":")[0].strip() for s in clearance_codes.split(",")]
                if clearance_codes
                else None
            )
            tool_codes = sub.get(TOOLS_HDR)
            tool_codes = (
                [s.split(":")[0].strip() for s in tool_codes.split(",")]
                if tool_codes
                else None
            )
            log.info(f"{emails} passed {clearance_codes}, tools {tool_codes}")
            return

        if changes:
            print_yaml(
                [
                    Msg.tmpl(
                        "clearance_change_summary",
                        target="#membership-automation",
                        changes=list(changes),
                        n=len(changes),
                    )
                ]
            )
        else:
            print_yaml([])
