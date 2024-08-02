"""Commands for handling violations of storage and other policies"""
import argparse
import datetime
import logging

import yaml

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import tznow  # pylint: disable=import-error
from protohaven_api.integrations import airtable  # pylint: disable=import-error
from protohaven_api.policy_enforcement import enforcer

log = logging.getLogger("cli.violations")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for violations"""

    @command(
        arg(
            "--reporter",
            help="who's reporting the violation",
            type=str,
            required=True,
        ),
        arg(
            "--suspect",
            help="who's suspected of causing the violation",
            type=str,
            default=None,
        ),
        arg(
            "--sections",
            help="comma-separated list of section IDs relevant to violation. See help for list",
            type=str,
            required=True,
        ),
        arg(
            "--fee", help="fee per day while violation is open", type=float, default=0.0
        ),
        arg("--notes", help="additional context", type=str, default=""),
    )
    def new_violation(self, args):
        """Create a new Violation in Airtable"""
        result = airtable.open_violation(
            args.reporter,
            args.suspect,
            args.sections.split(","),
            None,
            tznow(),
            args.fee,
            args.notes,
        )
        print(result)

    @command(
        arg(
            "--id",
            help="instance number for the violation",
            type=int,
            required=True,
        ),
        arg(
            "--closer",
            help="who's closing the violation",
            type=str,
            required=True,
        ),
        arg(
            "--suspect",
            help="suspect (if known)",
            type=str,
        ),
        arg(
            "--notes",
            help="any additionald details",
            type=str,
        ),
    )
    def close_violation(self, args):
        """Close out a violation so consequences cease"""
        result, content = airtable.close_violation(
            args.id, args.closer, tznow(), args.suspect, args.notes
        )
        print(result.status_code, content)

    @command(
        arg(
            "--apply",
            help=(
                "Apply fees and suspension actions in Airtable. "
                "If false, they will only be printed"
            ),
            action=argparse.BooleanOptionalAction,
            default=False,
        )
    )
    def enforce_policies(self, args):  # pylint: disable=too-many-locals
        """Follows suspension & violation logic for any ongoing violations.
        For any violation tagged with a user, generate comms.
        For any action needed to suspend users, generate comms.
        Also generate a summary of changes for sending to Discord."""
        violations = airtable.get_policy_violations()
        old_fees = [
            (f["fields"]["Violation"][0], f["fields"]["Amount"], f["fields"]["Created"])
            for f in airtable.get_policy_fees()
            if not f["fields"].get("Paid")
        ]
        new_fees = enforcer.gen_fees(violations)
        if len(new_fees) > 0:
            log.info("Generated fees:")
            for f in new_fees:
                log.info(f" - {f[2]} {f[0]} ${f[1]}")
            if args.apply:
                rep = airtable.create_fees(new_fees)
                log.debug(f"{rep.status_code}: {rep.content}")
                log.info(f"Applied {len(new_fees)} fee(s) into Airtable")
            else:
                log.warning("--apply not set; no fee(s) will be added")

        new_sus = enforcer.gen_suspensions()
        if len(new_sus) > 0:
            log.info("Generated suspensions:")
            for s in new_sus:
                log.info(f" - {s}")
            if args.apply:
                for neon_id, duration, violation_ids in new_sus:
                    start = tznow()
                    end = start + datetime.timedelta(duration)
                    rep = airtable.create_suspension(neon_id, violation_ids, start, end)
                    log.debug(f"{rep.status_code}: {rep.content}")
                log.info(f"Applied {len(new_sus)} suspension(s) into Airtable")
            else:
                log.warning("--apply not set; no suspension(s) will be added")

        # Update accrual totals so they're visible at protohaven.org/violations
        enforcer.update_accruals()

        result = enforcer.gen_comms(violations, old_fees, new_fees, new_sus)

        print(yaml.dump(result, default_flow_style=False, default_style=""))
        log.info(f"Generated {len(result)} notification(s)")
