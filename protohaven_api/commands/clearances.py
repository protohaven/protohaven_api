"""Commands related operations on Dicsord"""

import argparse
import datetime
import logging
import re
from collections import defaultdict

from protohaven_api.automation.membership.clearances import resolve_codes
from protohaven_api.automation.membership.clearances import update as update_clearances
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tz, tznow
from protohaven_api.integrations import neon, sheets
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.clearances")

PASS_HDR = "Protohaven emails of each student who PASSED (This should be the email address they used to sign up for the class or for their Protohaven account). If none of them passed, enter N/A."  # pylint: disable=line-too-long
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
            "--after_days_ago",
            help="Handle instructor logs after this many days ago",
            type=int,
            default=30,
        ),
        arg(
            "--max_users_affected",
            help="Only allow at most this number of users to receive clearance changes",
            type=int,
            default=5,
        ),
    )
    def sync_clearances(  # pylint: disable=too-many-locals, too-many-statements, too-many-branches
        self, args, _
    ):
        """Fetches clearances in the Master Instructor Hours and Clearance Log,
        expands them to individual tool codes, and updates accounts in Neon CRM with
        assigned clearances.

        This is a "backfill" equivalent to the AppScript automation that runs on form
        submission.
        """
        if not args.apply:
            log.warning(
                "***** --apply not set; clearances will not actually change *****"
            )
        user_filter = (
            {e.lower() for e in args.filter_users.split(",")}
            if args.filter_users
            else None
        )
        dt = tznow() - datetime.timedelta(days=args.after_days_ago)

        log.info("Fetching clearance codes")
        all_codes = {c["name"].split(":")[0] for c in neon.fetch_clearance_codes()}
        log.info(f"All codes: {all_codes}")

        log.info(f"Building list of clearances starting from {dt}")
        earned = defaultdict(set)
        for sub in sheets.get_instructor_submissions():
            if sub["Timestamp"].astimezone(tz) < dt:
                continue
            emails = sub.get(PASS_HDR)
            mm = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", emails)
            if not mm:
                log.warning(f"No valid emails parsed from row: {emails}")
            emails = [
                m.replace("(", "").replace(")", "").replace(",", "").strip() for m in mm
            ]

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
            for e in emails:
                if user_filter and e.lower() not in user_filter:
                    continue
                if clearance_codes:
                    earned[e.strip()].update(resolve_codes(clearance_codes))
                if tool_codes:
                    earned[e.strip()].update(tool_codes)
        log.info(f"Clearance list built; {len(earned)} users in list")

        changes = []
        errors = []
        invalids = set()
        log.info("Earned clearances:")
        for email, clr in earned.items():
            clr = {c for c in clr if not c.strip().lower() == "n/a"}
            clr_validated = set(c for c in clr if c in all_codes)
            if len(clr) != len(clr_validated):
                log.warning(
                    f"Ignoring invalid clearances for {email}: {clr - clr_validated}"
                )
                invalids.update(clr - clr_validated)
            try:
                mutations = update_clearances(
                    email, "PATCH", clr_validated, apply=args.apply
                )
                if len(mutations) > 0:
                    changes.append(f"{email}: added {', '.join(mutations)}")
                    log.info(changes[-1])
            except TypeError as err:
                log.warning(str(err))
                errors.append(str(err))
            except KeyError as err:
                log.warning(str(err))
                errors.append(str(err))

        if len(invalids) > 0:
            errors.append(
                "Found one or more instances of the following invalid clearances: "
                + ", ".join(invalids)
            )

        if len(changes) > 0:
            print_yaml(
                [
                    Msg.tmpl(
                        "clearance_change_summary",
                        target="#membership-automation",
                        changes=list(changes),
                        errors=list(errors),
                        n=len(changes),
                    )
                ]
            )
        else:
            print_yaml([])
