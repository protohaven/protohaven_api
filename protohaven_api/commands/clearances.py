"""Commands related operations on Dicsord"""

import argparse
import datetime
import logging
from collections import defaultdict

from protohaven_api.automation.membership import clearances
from protohaven_api.automation.membership.clearances import RecertsDict
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, neon, sheets
from protohaven_api.integrations.airtable import NeonID, RecordID, ToolCode
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.clearances")

type PendingRecerts = dict[tuple[NeonID, ToolCode], airtable.PendingRecert]


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
        for (
            email,
            tool_codes,
            _,
        ) in sheets.get_passing_student_clearances(dt=dt, from_row=args.from_row):
            if user_filter and email.lower() not in user_filter:
                continue
            if tool_codes:
                earned[email.strip()].update(tool_codes)
        log.info(f"Clearance list built; {len(earned)} users in list")

        changes = []
        errors = []
        invalids = set()
        log.info("Earned clearances:")
        for email, clr in earned.items():
            log.info(f"{email}: {clr}")
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
        self, needed: RecertsDict, pending: PendingRecerts
    ) -> dict[
        NeonID,
        list[
            tuple[
                ToolCode, datetime.datetime, datetime.datetime, str | None, bool | None
            ]
        ],
    ]:
        """Add new pending recertifications to Airtable.

        The `inst_deadline` (deadline based on instruction/quizzes) of the
        recertification is added, NOT the `res_deadline` (deadline based on
        reservations).

        This is because reservations only *delays* the deadline, whereas
        new instruction fully *replaces* the deadline.
        """
        new_additions_by_member = defaultdict(list)
        for k, v in needed.items():
            neon_id, tool_code = k
            inst_deadline, res_deadline = v
            # We re-add existing pending records if they were never notified
            # But we take a note of the record ID so we don't duplicate them
            cur = pending.get((neon_id, tool_code))
            if not cur or not cur.notified:
                new_additions_by_member[neon_id].append(
                    (
                        tool_code,
                        inst_deadline,
                        res_deadline,
                        cur.rec_id if cur and not cur.notified else None,
                        cur.suspended if cur else None,
                    )
                )
        return dict(new_additions_by_member)

    def _stage_remove_pending_not_needed(
        self, not_needed: RecertsDict, pending: PendingRecerts
    ) -> dict[NeonID, list[tuple[RecordID, ToolCode, datetime.datetime]]]:
        removals_by_member = defaultdict(list)
        now = tznow()
        for k, v in not_needed.items():
            neon_id, tool_code = k
            inst_deadline, res_deadline = v
            if (neon_id, tool_code) not in pending:
                continue

            cur = pending.get((neon_id, tool_code))
            if not cur or not cur.rec_id:
                continue

            # There are two cases where we want to remove pending recerts.
            # Case 1: member reserved tools a bunch while they weren't yet suspended.
            # In this case they've "recovered" their clearance.
            # Case 2: member's clearance is suspended, but they took instruction. This
            # is the normal recert process.
            #
            # Making a bunch of tool reservations shouldn't allow the user to get
            # back into recert state if their clearance has been suspended.
            if (res_deadline > now and not cur.suspended) or (inst_deadline > now):
                new_deadline = max(inst_deadline, res_deadline)
                removals_by_member[neon_id].append(
                    (cur.rec_id, tool_code, new_deadline)
                )
        return removals_by_member

    def _stage_suspend_due_clearances(
        self,
        now,
        pending: PendingRecerts,
        needed: RecertsDict,
    ) -> dict[NeonID, list[tuple[RecordID, ToolCode, datetime.datetime]]]:
        by_user = defaultdict(list)
        for k, v in needed.items():
            neon_id, tool_code = k
            inst_deadline, res_deadline = v
            deadline = max(inst_deadline, res_deadline)
            p = pending.get((neon_id, tool_code))
            # We want to suspend clearances that have been announced, are due,
            # and are not already suspended
            if p and p.notified and now >= deadline and not p.suspended:
                by_user[neon_id].append((p.rec_id, tool_code, deadline))
        return dict(by_user)

    @classmethod
    def tidy_recertification_table(cls, pending: PendingRecerts, needed: RecertsDict):
        """Keeps deadlines in recertifications table up to date"""
        for p in pending.values():
            cur = needed.get((p.neon_id, p.tool_code))
            if not cur:
                continue
            next_inst_deadline, next_res_deadline = cur
            log.info(f"{next_inst_deadline} vs {p.inst_deadline}")
            if (
                next_inst_deadline != p.inst_deadline
                or next_res_deadline != p.res_deadline
            ):
                log.info(
                    str(
                        airtable.update_pending_recertification(
                            p.rec_id,
                            inst_deadline=next_inst_deadline,
                            res_deadline=next_res_deadline,
                        )
                    )
                )

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
            "--filter_tool_codes",
            help="Restrict to comma separated list of tool codes (e.g. LS1)",
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
            {e.strip() for e in args.filter_users.split(",")}
            if args.filter_users
            else None
        )
        if user_filter:
            log.warning(
                f"Filtering to only affecting these Neon IDs: "
                f"{', '.join([str(i) for i in user_filter])}"
            )
        tool_code_filter = (
            {t.strip() for t in args.filter_tool_codes.split(",")}
            if args.filter_tool_codes
            else None
        )
        if tool_code_filter:
            log.warning(
                f"Filtering to only affecting these tool codes: "
                f"{', '.join(tool_code_filter)}"
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

        log.info("Fetching environment")
        env = clearances.build_recert_env(from_date, args.from_row)
        log.info(f"Pending: {env.pending}")
        if tool_code_filter:
            env.recert_configs = {
                k: v for k, v in env.recert_configs.items() if k in tool_code_filter
            }
        log.info(
            f"Tools with recert configs (filtered): {', '.join(env.recert_configs.keys())}"
        )
        needed, not_needed = clearances.segment_by_recertification_needed(
            env, max_pending_date
        )
        log.info(f"Needed: {needed}")
        log.info(f"Not needed: {not_needed}")

        log.info("Staging needed operations")
        new_pendings = self._stage_new_pending_recerts(needed, env.pending)
        log.info(f"new pendings for Neon IDs: {list(new_pendings.keys())}")
        rm_pendings = self._stage_remove_pending_not_needed(not_needed, env.pending)
        log.info(f"rm pendings for Neon IDs: {list(rm_pendings.keys())}")
        rm_clearances = self._stage_suspend_due_clearances(now, env.pending, needed)
        log.info(f"rm_clearances for Neon IDs: {list(rm_clearances.keys())}")

        affected_neon_ids = set(
            list(new_pendings.keys())
            + list(rm_pendings.keys())
            + list(rm_clearances.keys())
        )
        log.info(f"Affected neon IDs: {', '.join(affected_neon_ids)}")
        filtered_neon_ids = (
            affected_neon_ids.intersection(user_filter)
            if user_filter
            else affected_neon_ids
        )
        log.info(f"Affected neon IDs (filtered): {', '.join(filtered_neon_ids)}")
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
            records_for_comms = []
            mutations = []
            if args.apply:
                for tool_code, inst_deadline, res_deadline, rec, _ in new_pending:
                    log.info(
                        f"#{neon_id}: pending tool_code={tool_code}, "
                        f"deadline={inst_deadline}"
                    )
                    if not rec:
                        _, content = airtable.insert_pending_recertification(
                            neon_id, tool_code, inst_deadline, res_deadline
                        )
                        records_for_comms += [r["id"] for r in content["records"]]
                    else:
                        records_for_comms.append(rec)

                if len(rm_pending) > 0:
                    delta = [tc for _, tc, _ in rm_pending]
                    log.info(f"Patching clearances for {neon_id}: {delta}")
                    mutations = clearances.update_by_neon_id(
                        neon_id, "PATCH", delta, apply=args.apply
                    )
                    log.info(f"Mutations done: {mutations}")

                for rec, _, _ in rm_pending:
                    log.info(f"#{neon_id}: rm pending record {rec}")
                    log.info(str(airtable.remove_pending_recertification(rec)))

                rm_codes = [tc for _, tc, _ in rm_clearance]
                if len(rm_codes) > 0:
                    log.info(f"#{neon_id}: suspend {rm_codes}")
                    log.info(
                        str(
                            clearances.update_by_neon_id(
                                neon_id, "DELETE", rm_codes, apply=True
                            )
                        )
                    )
                for rec, _, _ in rm_clearance:
                    log.info(
                        str(
                            airtable.update_pending_recertification(rec, suspended=True)
                        )
                    )

            summary = []
            if len(new_pending) > 0:
                summary.append(f"add pending {', '.join([p[0] for p in new_pending])}")
            if len(rm_pending) > 0:
                summary.append(
                    f"remove pending {', '.join([tc for _, tc, _ in rm_pending])}"
                )
            if len(rm_clearance) > 0:
                summary.append(
                    f"suspend clearances {', '.join([tc for _, tc, _ in rm_clearance])}"
                )
            if len(mutations) > 0:
                summary.append(f"patch in clearances {', '.join(mutations)}")
            changes.append(f"#{neon_id}: {', '.join(summary)}")
            log.info(changes[-1])

            log.info(f"Building comms for #{neon_id}")
            fname, email = env.contact_info.get(str(neon_id)) or (None, None)
            if not email:
                changes.append(
                    f"WARNING: Contact info not found for #{neon_id}; skipping notification"
                )
                log.warning(changes[-1])
                continue

            def _fmt_date(d):
                return d.strftime("%Y-%m-%d") if d else None

            msg = Msg.tmpl(
                "member_recert_update",
                fname=fname,
                new_pending=[
                    {
                        "tool_name": getattr(
                            env.recert_configs.get(tc, {}), "tool_name"
                        )
                        or tc,
                        "last_earned": _fmt_date(env.last_earned.get((neon_id, tc))),
                        "due_date": _fmt_date(max(inst_deadline, res_deadline)),
                    }
                    for tc, inst_deadline, res_deadline, _, _ in new_pending
                ],
                rm_pending=[
                    {
                        "tool_name": getattr(
                            env.recert_configs.get(tc, {}), "tool_name"
                        )
                        or tc,
                        "last_earned": _fmt_date(env.last_earned.get((neon_id, tc))),
                        "next_deadline": _fmt_date(new_deadline),
                    }
                    for _, tc, new_deadline in rm_pending
                ],
                rm_clearance=[
                    {
                        "tool_name": getattr(
                            env.recert_configs.get(tc, {}), "tool_name"
                        )
                        or tc,
                        "last_earned": _fmt_date(env.last_earned.get((neon_id, tc))),
                        "due_date": _fmt_date(deadline),
                    }
                    for _, tc, deadline in rm_clearance
                ],
                target=email,
                recerts=records_for_comms,
            )
            # Prevent duplicate messages; body is rendered on creation
            assert msg.body
            msg.id = f"{neon_id}:{hash(msg.body)}"
            comms.append(msg)

        log.info("Tidying up Recertifications table")
        self.tidy_recertification_table(env.pending, needed)

        if len(changes) > 0:
            comms.append(
                Msg.tmpl(
                    "recertification_summary",
                    target="#membership-automation",
                    changes=list(changes),
                )
            )
        print_yaml(comms)
