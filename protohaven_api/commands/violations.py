"""Commands for handling violations of storage and other policies"""
import argparse
import datetime
import logging

from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tznow  # pylint: disable=import-error
from protohaven_api.integrations import airtable  # pylint: disable=import-error
from protohaven_api.policy_enforcement import enforcer

log = logging.getLogger("cli.violations")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for violations"""

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
        print_yaml(result)
        log.info(f"Generated {len(result)} notification(s)")
