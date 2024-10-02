""" A set of command line tools, possibly run by CRON"""

import argparse
import datetime
import logging
import sys
from collections import defaultdict

import yaml

from protohaven_api.commands import classes
from protohaven_api.commands import comms as ccomms
from protohaven_api.commands import (
    development,
    finances,
    forwarding,
    maintenance,
    reservations,
    roles,
    violations,
)
from protohaven_api.config import get_config, tznow
from protohaven_api.docs_automation.docs import validate as validate_docs
from protohaven_api.integrations import comms, neon, tasks
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.rbac import Role

cfg = get_config()
logging.basicConfig(level=cfg["general"]["log_level"].upper())
log = logging.getLogger("cli")
server_mode = cfg["general"]["server_mode"].lower()
log.info(f"Mode is {server_mode}\n")
init_connector(dev=server_mode != "prod")

run_discord_bot = cfg["discord_bot"]["enabled"].lower() == "true"
if run_discord_bot:
    import threading
    import time

    from protohaven_api.discord_bot import run as run_bot

    threading.Thread(target=run_bot, daemon=True).start()
    time.sleep(
        2.0
    )  # Hacky - should use `wait_until_ready` but there's threading problems
else:
    log.debug("Skipping startup of discord bot")


def purchase_request_alerts():
    """Send alerts when there's purchase requests that haven't been acted upon for some time"""
    content = "**Open Purchase Requests Report:**"
    sections = defaultdict(list)
    counts = defaultdict(int)
    now = tznow()
    thresholds = {
        "low_pri": 7,
        "high_pri": 2,
        "class_supply": 3,
        "on_hold": 30,
        "unknown": 0,
    }
    headers = {
        "low_pri": "Low Priority",
        "high_pri": "High Priority",
        "class_supply": "Class Supplies",
        "on_hold": "On Hold",
        "unknown": "Unknown/Unparsed Tasks",
    }

    def format_request(t):
        if (t["modified_at"] - t["created_at"]).days > 1:
            dt = (now - t["modified_at"]).days
            dstr = f"modified {dt}d ago"
        else:
            dt = (now - t["created_at"]).days
            dstr = f"created {dt}d ago"
        return (f"- {t['name']} ({dstr})", dt)

    for t in tasks.get_open_purchase_requests():
        counts[t["category"]] += 1
        thresh = now - datetime.timedelta(days=thresholds[t["category"]])
        if t["created_at"] < thresh and t["modified_at"] < thresh:
            sections[t["category"]].append(format_request(t))

    # Sort oldest to youngest, by section
    for k, v in sections.items():
        v.sort(key=lambda t: -t[1])
        sections[k] = [t[0] for t in v]

    section_added = False
    for k in ("high_pri", "class_supply", "low_pri", "on_hold", "unknown"):
        if len(sections[k]) > 0:
            section_added = True
            content += f"\n\n{headers[k]} ({counts[k]} total open; "
            content += f"showing only tasks older than {thresholds[k]} days):\n"
            content += "\n".join(sections[k])

    if not section_added:
        content += "\nAll caught up. Nice."

    log.info(content)
    comms.send_board_message(content)
    log.info("Done")


class ProtohavenCLI(  # pylint: disable=too-many-ancestors
    ccomms.Commands,
    reservations.Commands,
    classes.Commands,
    forwarding.Commands,
    finances.Commands,
    development.Commands,
    violations.Commands,
    roles.Commands,
    maintenance.Commands,
):
    """argparser-based CLI for protohaven operations"""

    def __init__(self):
        helptext = "\n".join(
            [
                f"{a}: {getattr(self, a).__doc__}"
                for a in dir(self)
                if not a.startswith("__")
            ]
        )
        parser = argparse.ArgumentParser(
            description="Protohaven CLI",
            usage=f"{sys.argv[0]} <command> [<args>]\n\n{helptext}\n\n\n",
        )
        parser.add_argument("command", help="Subcommand to run")
        args = parser.parse_args(sys.argv[1:2])  # Limit to only initial command args
        if not hasattr(self, args.command):
            parser.print_help()
            sys.exit(1)
        getattr(self, args.command)(
            sys.argv[2:]
        )  # Ignore first two argvs - already parsed

    def validate_docs(self, argv):  # pylint: disable=too-many-statements
        """Go through list of tools in airtable, ensure all of them have
        links to a tool guide and a clearance doc that resolve successfully"""
        parser = argparse.ArgumentParser(description=self.validate_docs.__doc__)
        parser.parse_args(argv)
        result = validate_docs()
        print(yaml.dump([result], default_flow_style=False, default_style=""))

    def validate_member_clearances(self, argv):
        """Confirm clearance pipeline is correctly pushing clearances into Neon."""
        raise NotImplementedError("TODO implement")

    def sync_team_page(self, argv):
        """Get profile pictures of board, shop techs, and staff and sync them
        to the protohaven site"""
        parser = argparse.ArgumentParser(description=self.gen_maintenance_tasks.__doc__)
        parser.add_argument(
            "--apply",
            help="if false, don't actually sync",
            action=argparse.BooleanOptionalAction,
            default=False,
        )
        # print(neon.fetch_output_fields())
        parser.parse_args(argv)
        for m in neon.get_members_with_role(Role.SHOP_TECH, ["Photo URL"]):
            print(m)
        raise NotImplementedError("Sync not yet implemented")


ProtohavenCLI()
