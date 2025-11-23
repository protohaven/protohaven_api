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

    def _add_new_pending_recerts(self, needed, pending, apply):
        new_additions_by_member = defaultdict(list)
        for neon_id, tool_code, deadline in needed:
            if (neon_id, tool_code) not in pending:
                log.info(f"New addition: ID {neon_id}, tool code {tool_code} deadline {deadline}")
                if apply:
                    log.info(
                        str(
                            airtable.insert_pending_recertification(
                                neon_id, tool_code, deadline
                            )
                        )
                    )
                new_additions_by_member[neon_id].append(tool_code)
        return new_additions_by_member


    def _remove_not_needed_pending(self, not_needed, pending, apply):
        removed = defaultdict(list)
        for neon_id, tool_code, next_deadline in not_needed:
            rec, deadline = pending.get((neon_id, tool_code))
            if rec:
                removed[neon_id].append((rec, tool_code, prev_deadline, next_deadline))
                log.info(str(airtable.remove_pending_recertification(rec)))
        return removed


    def _revoke_pending_due(self, now, not_needed, neon_clearances):
        revocation_by_user = defaultdict(list)
        for (
            neon_id,
            tool_code,
            deadline,
            rec_id,
        ) in airtable.get_pending_recertifications():
            if now < deadline or (neon_id, tool_code) in not_needed:
                continue
            if tool_code not in (neon_clearances.get(neon_id) or []):
                continue
            revocation_by_user[neon_id].append(tool_code)
        log.info(
            "Revoking clearances for past-due recertifications of "
            f"{len(revocation_by_user)} user(s)"
        )
        for neon_id, tool_codes in revocation_by_user.items():
            log.info(f"DELETE Neon ID {neon_id}; Tool Codes {tool_codes}")
            mutations = clearances.update_by_neon_id(
                neon_id, "DELETE", tool_codes, apply=args.apply
            )
        return revocation_by_user

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
    def recertification(
        self, args, _
    ):  # pylint: disable=too-many-branches,too-many-locals
        """Schedules pending recertifications in Airtable for members based on when they received
        instruction, when they took quizzes, and the cumulative reservation hours of related
        tools.
        """

        now = tznow()
        from_date = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - datetime.timedelta(days=args.reservation_lookbehind_days)
        changes: list[str] = []
        comms = []

        log.info(f"Fetching all pending recertification state, beginning at {from_date}")
        pending = {
            (neon_id, tool_code): (rec_id, deadline)
            for neon_id, tool_code, deadline, rec_id in airtable.get_pending_recertifications()
        }

        log.info("Fetching tool name mapping")
        tool_name_map = {
            t["fields"].get("Tool Code", "").strip().upper(): t["fields"].get("Tool Name")
                for t in get_tools()
        }

        log.info("Fetching state of members' clearances")
        env = clearances.build_recert_env(from_date, args.from_row)
        needed, not_needed = clearances.segment_by_recertification_needed(env)

        log.info("Adding any needed recerts not already in table")
        new_additions_by_member = self._add_new_pending_recerts(needed, pending, args.apply)
        log.info("Building emails for newly pending recerts")
        for neon_id, tool_codes in new_additions_by_member.items():
            changes.append(f"#{neon_id}: trigger recerts {tool_codes}")
            fname, email = env.contact_info.get(neon_id) or None, None
            if not email:
                continue
            comms.append(Msg.tmpl("user_recert_pending",
                    fname=fname,
                    recert=[
                        {
                            "tool_name": tool_name_map.get(tc) or tc,
                            "last_earned": env.last_earned.get((neon_id, tc)) or "N/A",
                            "due_date": pending[(neon_id, tc)][1]
                        } for tc in tool_codes
                    ], # tool name, last earned, due date
                    target=email,
                    id=f"{neon_id}:{tool_codes}",
            ))

        log.info("Resolving any not-needed recerts that are in the table")
        rm_pendings = self._remove_not_needed_pending(not_needed, pending, args.apply)

        log.info("Building emails for no-longer-pending recertifications")
        for neon_id, pp in rm_pendings.items():
            tool_codes = [tc for _, tc in pp]
            changes.append(f"#{neon_id}: remove pending recerts {tool_codes}")
            log.info(changes[-1])
            fname, email = env.contact_info.get(neon_id) or None, None
            if not email:
                continue

            comms.append(Msg.tmpl("user_recert_no_longer_pending",
                    fname=fname,
                    recert=[
                        {
                            "tool_name": tool_name_map.get(tc) or tc,
                            "last_earned": env.last_earned.get((neon_id, tc)) or "N/A",
                            "prev_deadline": pending[(neon_id, tc)][1],
                            "next_deadline": None,
                        } for _, tool_code, prev_deadline, next_deadline in pp
                    ], # tool name, last earned, due date
                    target=email,
                    id=f"{neon_id}:{tool_codes}",
            ))

        revoked = self._revoke_pending_due(now, not_needed, env.neon_clearances)
        for neon_id, tool_codes in revoked.items():
            changes.append(
                f"#{neon_id}: removed {', '.join(mutations)} (recert due)"
            )
            log.info(changes[-1])
            comms.append(Msg.tmpl("user_recert_clearances_revoked",
                    fname=env.neon_id_to_fname.get(neon_id) or "member",
                    recert=,
                    target=,
                    id=,
            ))

        if len(changes) > 0:
            comms.append(Msg.tmpl(
                        "recertification_summary",
                        target="#membership-automation",
                        changes=list(changes),
                    ))
        print_yaml(comms)
