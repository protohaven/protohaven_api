"""Commands related to facility and equipment maintenance"""
import argparse
import logging

from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import exec_details_footer  # pylint: disable=import-error
from protohaven_api.maintenance import comms as mcomms
from protohaven_api.maintenance import manager

log = logging.getLogger("cli.maintenance")


class Commands:
    """Commands for managing maintenance tasks"""

    @command(
        arg(
            "--apply",
            help="actually create new Asana tasks",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
    )
    def gen_maintenance_tasks(self, args):
        """Check recurring tasks list in Airtable, add new tasks to asana
        And notify techs about new and stale tasks that are tech_ready."""
        tt = manager.run_daily_maintenance(args.apply)
        subject, body, is_html = mcomms.daily_tasks_summary(tt)
        report = {
            "id": "daily_maintenance",
            "target": "#techs-live",
            "subject": subject,
            "body": body,
            "html": is_html,
        }
        print_yaml([report])

    @command()
    def gen_tech_leads_maintenance_summary(self, _):
        """Report on status of equipment maintenance & stale tasks"""
        stale = manager.get_stale_tech_ready_tasks()
        report = []
        if len(stale) > 0:
            log.info(f"Found {len(stale)} stale tasks")
            subject, body, is_html = mcomms.tech_leads_summary(
                stale, manager.DEFAULT_STALE_DAYS
            )
            report = [
                {
                    "id": "daily_maintenance",
                    "target": "#techs-leads",
                    "subject": subject,
                    "body": body + exec_details_footer(),
                    "html": is_html,
                }
            ]
        print_yaml(report)
