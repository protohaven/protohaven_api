"""Commands for handling violations of storage and other policies"""

import argparse
import logging

from protohaven_api.automation.policy import enforcer
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.integrations import airtable  # pylint: disable=import-error

log = logging.getLogger("cli.violations")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for violations"""

    @command(
        arg(
            "--apply",
            help="If true, apply fees in Airtable",
            action=argparse.BooleanOptionalAction,
            default=False,
        )
    )
    def enforce_policies(self, args, _):
        """Follows violation logic for any ongoing violations.
        For any violation tagged with a user, generate comms.
        For any action needed to suspend users, generate comms.
        Also generate a summary of changes for sending to Discord."""
        violations = airtable.get_policy_violations()
        old_fees = [
            (f["fields"]["Violation"][0], f["fields"]["Amount"], f["fields"]["Created"])
            for f in airtable.get_policy_fees()
            if not f["fields"].get("Paid")
            and f["fields"].get("Violation")
            and f["fields"].get("Amount")
            and f["fields"].get("Created")
        ]
        new_fees = enforcer.gen_fees(violations)
        if len(new_fees) > 0:
            log.info("Generated fees:")
            for f in new_fees:
                log.info(f" - {f[2]} {f[0]} ${f[1]}")
            if args.apply:
                status, content = airtable.create_fees(new_fees)
                log.debug(f"{status}: {content}")
                log.info(f"Applied {len(new_fees)} fee(s) into Airtable")
            else:
                log.warning("--apply not set; no fee(s) will be added")

        # Update accrual totals so they're visible at protohaven.org/violations
        enforcer.update_accruals()
        result = enforcer.gen_comms(violations, old_fees, new_fees)
        print_yaml(result)
        log.info(f"Generated {len(result)} notification(s)")
