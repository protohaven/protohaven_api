"""Commands related operations on Dicsord"""

import argparse
import datetime
import logging
from collections import defaultdict

from protohaven_api.automation.membership import clearances
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, neon, sheets
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.clearances")


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
        arg(
            "--from_row",
            help="Set the row of the instructor log sheet to start at - set this higher"
            " to prevent read timeouts and network errors due to the amount of data.",
            type=int,
            default=1300,
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
        for email, clearance_codes, tool_codes in sheets.get_passing_student_clearances(
            dt=dt, from_row=args.from_row
        ):
            if user_filter and email.lower() not in user_filter:
                continue
            if clearance_codes:
                earned[email.strip()].update(clearances.resolve_codes(clearance_codes))
            if tool_codes:
                earned[email.strip()].update(tool_codes)
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
                mutations = clearances.update(
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
            "--days_ahead",
            help="Set recert deadline at least this many days ahead of the current day",
            type=int,
            default=30,
        ),
        arg(
            "--max_users_affected",
            help="Only allow at most this number of users to have recert",
            type=int,
            default=5,
        ),
        arg(
            "--from_row",
            help="Set the row of the instructor log sheet to start at - set this higher"
            " to prevent read timeouts and network errors due to the amount of data.",
            type=int,
            default=1300,
        ),
        arg(
            "--reservation_lookbehind_days",
            help="Look this far back in reservations to identify tool usage",
            type=int,
            default=90,
        ),
    )
    def recertification(self, args, _):
        """Schedules pending recertifications in Airtable for members based on when they received
        instruction, when they took quizzes, and the cumulative reservation hours of related
        tools.
        """

        from_date = tznow().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - datetime.timedelta(days=args.reservation_lookbehind_days)
        deadline = tznow().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + datetime.timedelta(days=args.days_ahead)
        changes = []

        log.info("Fetching all pending recertification state")
        pending = {
            (neon_id, tool_code): rec_id
            for neon_id, tool_code, deadline, rec_id in airtable.get_pending_recertifications()
        }

        log.info("Fetching state of members' clearances")
        needed, not_needed = clearances.find_members_needing_recert_by(
            from_date, deadline, args.from_row
        )

        log.info("Adding any needed recerts not already in table")
        for neon_id, tool_code in needed:
            if (neon_id, tool_code) not in pending:
                log.info(f"New addition: ID {neon_id}, tool codes {tool_code}")
                if args.apply:
                    log.info(
                        str(
                            airtable.insert_pending_recertification(
                                neon_id, tool_code, deadline
                            )
                        )
                    )
                    changes.append(f"#{neon_id}: trigger recert {tool_code}")

        log.info("Resolving any not-needed recerts that are in the table")
        not_needed_by_user = defaultdict(list)
        for neon_id, tool_code in not_needed:
            not_needed_by_user[neon_id].append(tool_code)
        for neon_id, tool_codes in not_needed_by_user.items():
            log.info(f"Neon ID {neon_id}; Tool Code {tool_code}")
            mutations = clearances.update_by_neon_id(
                neon_id, "PATCH", tool_codes, apply=args.apply
            )
            if len(mutations) > 0:
                changes.append(f"#{neon_id}: added {', '.join(mutations)}")
                log.info(changes[-1])

            for tool_code in tool_codes:
                rec = pending.get((neon_id, tool_code))
                if not rec:
                    continue
                log.info("Removing pending recert: {neon_id}, {tool_code}")
                log.info(str(airtable.remove_pending_recertification(rec)))
