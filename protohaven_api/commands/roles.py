"""Commands related operations on Dicsord"""
import argparse
import logging
import re
from datetime import datetime

import yaml
from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import tz, tznow  # pylint: disable=import-error
from protohaven_api.integrations import (  # pylint: disable=import-error
    airtable,
    neon,
    sheets,
    tasks,
)

log = logging.getLogger("cli.roles")


class Commands:
    """Commands for managing roles of members"""

    @command(
        arg(
            "--apply",
            help="when true, Asana tasks are completed when comms are generated",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def sync_discord_roles():
        """Syncs the roles in discord with the state of membership and custom fields in Neon"""
        role_intent = defaultdict(list) # map discord ID to list of roles
        for r in (Role.INSTRUCTOR, Role.BOARD_MEMBER, Role.STAFF, Role.SHOP_TECH_LEAD, Role.ONBOARDING):
            print(r)
            for m in neon.get_members_with_role(r, [neon.CustomField.DISCORD_USER]):
                if m.get('Discord User'):
                    print(m['Discord User'], "->", r)
                    role_intent[m['Discord User']].append(r)

        active_members = []
        for m in neon.get_active_members([neon.CustomField.DISCORD_USER]):
            if m.get('Discord User'):
                active_members.append(m['Discord User'])


        role_intent = dict(role_intent)
        log.info(f"Fetched {len(role_intent)} users' roles in Neon")
        log.info(f"Also {len(active_members)} active members with discord associations")
        print("Role intents:", role_intent)
        return json.dumps({
            "role_intent": role_intent,
            "active_members": active_members
            })

            
