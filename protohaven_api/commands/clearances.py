"""Commands related operations on Dicsord"""

import argparse
import datetime
import logging
from collections import defaultdict

from protohaven_api.automation.membership import clearances
from protohaven_api.automation.membership.clearances import Recert
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, neon, sheets
from protohaven_api.integrations.airtable import NeonID, RecordID, ToolCode
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.clearances")

type PendingRecerts = dict[tuple[NeonID, ToolCode], tuple[RecordID, datetime.datetime]]


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

    def _stage_new_pending_recerts(
        self, needed: set[Recert], pending: PendingRecerts
    ) -> dict[NeonID, list[tuple[ToolCode, datetime.datetime, datetime.datetime]]]:
        """Add new pending recertifications to Airtable.

        The `inst_deadline` (deadline based on instruction/quizzes) of the
        recertification is added, NOT the `res_deadline` (deadline based on
        reservations).

        This is because reservations only *delays* the deadline, whereas
        new instruction fully *replaces* the deadline.
        """
        new_additions_by_member = defaultdict(list)
        for neon_id, tool_code, inst_deadline, res_deadline in needed:
            if (neon_id, tool_code) not in pending:
                # The actual deadline is whichever is greater between
                # instructor and reservation
                new_additions_by_member[neon_id].append(
                    (
                        tool_code,
                        inst_deadline,
                        res_deadline,
                    )
                )
        return dict(new_additions_by_member)

    def _stage_remove_pending_not_needed(
        self, not_needed: set[Recert], pending: PendingRecerts
    ) -> dict[NeonID, list[tuple[RecordID, ToolCode, datetime.datetime]]]:
        removals_by_member = defaultdict(list)
        for neon_id, tool_code, inst_deadline, res_deadline in not_needed:
            if (neon_id, tool_code) not in pending:
                continue
            new_deadline = max(inst_deadline, res_deadline)
            assert new_deadline > tznow()
            rec, _ = pending.get((neon_id, tool_code))
            if rec:
                removals_by_member[neon_id].append((rec, tool_code, new_deadline))
        return removals_by_member

    def _stage_revoke_due_clearances(
        self,
        now,
        pending: PendingRecerts,
        needed: set[Recert],
        neon_clearances: dict[NeonID, set[ToolCode]],
    ) -> dict[NeonID, list[tuple[ToolCode, datetime.datetime]]]:
        revocation_by_user = defaultdict(list)
        for (
            neon_id,
            tool_code,
            inst_deadline,
            res_deadline,
        ) in needed:
            deadline = max(inst_deadline, res_deadline)
            if now < deadline or (neon_id, tool_code) not in pending:
                continue
            if tool_code not in (neon_clearances.get(neon_id) or []):
                continue
            revocation_by_user[neon_id].append((tool_code, deadline))
        return revocation_by_user

    def _get_pending(self) -> PendingRecerts:
        return {
            (neon_id, tool_code): (rec_id, deadline)
            for neon_id, tool_code, deadline, rec_id in airtable.get_pending_recertifications()
        }

    def _tool_name_map(self):
        return {
            t["fields"]
            .get("Tool Code", "")
            .strip()
            .upper(): t["fields"]
            .get("Tool Name")
            for t in airtable.get_tools()
        }

    @command(
        arg(
            "--apply",
            help="when true, Neon is updated with clearances",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--filter_users",
            help="Restrict to comma separated list of Neon IDs",
            type=str,
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
            help="Look this far back in reservations to identify tool usage."
            " Note that individual tools have different intervals for which"
            " total usage is calculated.",
            type=int,
            default=90,
        ),
        arg(
            "--notify_expiring_before_days",
            help="Reservations expiring any time on or before this date will"
            " be added to the pending list and members will be notified",
            type=int,
            default=90,
        ),
    )
    def recertification(  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
        self, args, _
    ):
        """Schedules pending recertifications in Airtable for members based on when they received
        instruction, when they took quizzes, and the cumulative reservation hours of related
        tools.
        """

        if not args.apply:
            log.warning(
                "***** --apply not set; clearances and pending state will not "
                "actually change *****"
            )
        user_filter = (
            {int(e) for e in args.filter_users.split(",")}
            if args.filter_users
            else None
        )
        if user_filter:
            log.warning(
                f"Filtering to only affecting these Neon IDs: "
                f"{', '.join([str(i) for i in user_filter])}"
            )

        now = tznow().replace(hour=0, minute=0, second=0, microsecond=0)
        from_date = now - datetime.timedelta(days=args.reservation_lookbehind_days)
        max_pending_date = now + datetime.timedelta(
            days=args.notify_expiring_before_days
        )
        changes: list[str] = []
        comms = []

        log.info(
            f"Fetching all pending recertification state, beginning at {from_date}"
        )
        pending = self._get_pending()

        log.info("Fetching tool name mapping")
        tool_name_map = self._tool_name_map()

        log.info("Fetching state of members' clearances")
        env = clearances.build_recert_env(from_date, args.from_row)
        needed, not_needed = clearances.segment_by_recertification_needed(
            env, max_pending_date
        )

        log.info("Staging needed operations")
        new_pendings = self._stage_new_pending_recerts(needed, pending)
        rm_pendings = self._stage_remove_pending_not_needed(not_needed, pending)
        rm_clearances = self._stage_revoke_due_clearances(
            now, pending, needed, env.neon_clearances
        )

        affected_neon_ids = set(
            list(new_pendings.keys())
            + list(rm_pendings.keys())
            + list(rm_clearances.keys())
        )
        filtered_neon_ids = (
            affected_neon_ids.intersection(user_filter)
            if user_filter
            else affected_neon_ids
        )
        actions_by_member = [
            (
                n,
                new_pendings.get(n) or [],
                rm_pendings.get(n) or [],
                rm_clearances.get(n) or [],
            )
            for n in filtered_neon_ids
        ]

        for neon_id, new_pending, rm_pending, rm_clearance in sorted(
            actions_by_member,
            key=lambda a: len(a[1]) + len(a[2]) + len(a[3]),
            reverse=True,
        )[: args.max_users_affected]:
            assert len(new_pending) + len(rm_pending) + len(rm_clearance) > 0

            log.info(f"Applying changes for #{neon_id}")
            if args.apply:
                for tool_code, inst_deadline, _ in new_pending:
                    log.info(
                        f"#{neon_id}: insert pending tool_code={tool_code}, "
                        f"deadline={inst_deadline}"
                    )
                    log.info(
                        str(
                            airtable.insert_pending_recertification(
                                neon_id, tool_code, inst_deadline
                            )
                        )
                    )
                for rec, _, _ in rm_pending:
                    log.info(f"#{neon_id}: rm pending {rec}")
                    log.info(str(airtable.remove_pending_recertification(rec)))

                rm_codes = [tc for tc, _ in rm_clearance]
                if len(rm_codes) > 0:
                    log.info(f"#{neon_id}: revoke {rm_codes}")
                    log.info(
                        str(
                            clearances.update_by_neon_id(
                                neon_id, "DELETE", rm_codes, apply=True
                            )
                        )
                    )

            changes.append(
                f"#{neon_id}: add pending {', '.join([tc for tc, _, _ in new_pending])}"
                f"; remove pending {', '.join([tc for _, tc, _ in rm_pending])}"
                f"; revoke clearances {', '.join([tc for tc, _ in rm_clearance])}"
            )
            log.info(changes[-1])

            log.info(f"Building comms for #{neon_id}")
            fname, email = env.contact_info.get(neon_id) or None, None
            if not email:
                changes.append(
                    f"WARNING: Contact info not found for #{neon_id}; skipping notification"
                )
                log.warning(changes[-1])
                continue

            msg = Msg.tmpl(
                "member_recert_update",
                fname=fname,
                new_pending=[
                    {
                        "tool_name": tool_name_map.get(tc) or tc,
                        "last_earned": env.last_earned.get((neon_id, tc)) or "N/A",
                        "due_date": max(inst_deadline, res_deadline),
                    }
                    for tc, inst_deadline, res_deadline in new_pending
                ],
                rm_pending=[
                    {
                        "tool_name": tool_name_map.get(tc) or tc,
                        "last_earned": env.last_earned.get((neon_id, tc)) or "N/A",
                        "next_deadline": new_deadline,
                    }
                    for _, tc, new_deadline in rm_pending
                ],
                rm_clearance=[
                    {
                        "tool_name": tool_name_map.get(tc) or tc,
                        "last_earned": env.last_earned.get((neon_id, tc)) or "N/A",
                        "due_date": deadline,
                    }
                    for tc, deadline in rm_clearance
                ],
                target=email,
            )
            # Prevent duplicate messages; body is rendered on creation
            assert msg.body
            msg.id = f"{neon_id}:{hash(msg.body)}"
            comms.append(msg)

        if len(changes) > 0:
            comms.append(
                Msg.tmpl(
                    "recertification_summary",
                    target="#membership-automation",
                    changes=list(changes),
                )
            )
        print_yaml(comms)
