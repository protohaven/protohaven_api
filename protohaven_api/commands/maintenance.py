"""Commands related to facility and equipment maintenance"""
import argparse
import logging
import random

from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.comms_templates import Msg
from protohaven_api.maintenance import manager

log = logging.getLogger("cli.maintenance")


SALUTATIONS = [
    "Greetings techs!",
    "Hey there, techs!",
    "Salutations, techs!",
    "Hello techs!",
    "Howdy techs!",
    "Yo techs!",
    "Good day, techs!",
    "Hiya techs!",
    "Ahoy techs!",
    "Hey ho, techs!",
    "Beep boop, hello fellow techs!",
    "What's up, techs!",
    "Greetings and salutations, techs!",
    "Hi techs, ready to make something?",
    "Hey there, tech wizards!",
    "Top of the morning, techs!",
]

CLOSINGS = [
    "Keep sparking those creative circuits!",
    "For adventure and maker glory!",
    "Stay wired!",
    "Onwards to innovation!",
    "May your creativity be boundless!",
    "Stay charged and keep on making!",
    "Let's make some sparks!",
    "May your projects shine brighter than LEDs!",
    "Let's keep the gears turning and the ideas flowing!",
    "Until our next digital rendezvous, stay charged up!",
    "Dream it, plan it, do it!",
    "Innovation knows no boundaries - keep pushing forward!",
    "Every project is a step closer to greatness - keep going!",
    "Always be innovating!",
    "Stay curious, stay inspired, and keep making a difference!",
    "Remember - every circuit starts with a single connection. Keep connecting!",
    "Your passion fuels progress — keep the fire burning!",
    "You're not just making things, you're making history — keep on crafting!",
    "From concept to creation, keep the momentum!",
    "Invent, iterate, and inspire — the maker's trifecta!",
]

MAX_STALE_TASKS = 3


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
        print_yaml(
            Msg.tmpl(
                "tech_daily_tasks",
                salutation=random.choice(SALUTATIONS),
                closing=random.choice(CLOSINGS),
                new_count=len(tt),
                new_tasks=tt,
                id="daily_maintenance",
                target="#techs-live",
            )
        )

    @command()
    def gen_tech_leads_maintenance_summary(self, _):
        """Report on status of equipment maintenance & stale tasks"""
        stale = manager.get_stale_tech_ready_tasks()
        if len(stale) > 0:
            log.info(f"Found {len(stale)} stale tasks")
            stale.sort(key=lambda k: k["days_ago"], reverse=True)
            print_yaml(
                Msg.tmpl(
                    "tech_leads_maintenance_status",
                    stale_count=len(stale),
                    stale_thresh=manager.DEFAULT_STALE_DAYS,
                    stale_tasks=stale[:MAX_STALE_TASKS],
                    id="daily_maintenance",
                    target="#techs-leads",
                )
            )
