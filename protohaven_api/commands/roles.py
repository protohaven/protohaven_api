"""Commands related operations on Dicsord"""
import argparse
import json
import logging
from collections import defaultdict

from protohaven_api.commands.decorator import arg, command
from protohaven_api.integrations import neon  # pylint: disable=import-error
from protohaven_api.rbac import Role

log = logging.getLogger("cli.roles")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for managing roles of members"""

    @command(
        arg(
            "--apply",
            help="when true, Asana tasks are completed when comms are generated",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def sync_discord_roles(self, args):
        """Syncs the roles in discord with the state of membership and custom fields in Neon
        WARNING: WORK IN PROGRESS
        """
        log.warning("WARNING: THIS IS A WORK IN PROGRESS")
        role_intent = defaultdict(list)  # map discord ID to list of roles
        for r in (
            Role.INSTRUCTOR,
            Role.BOARD_MEMBER,
            Role.STAFF,
            Role.SHOP_TECH_LEAD,
            Role.ONBOARDING,
        ):
            print(r)
            for m in neon.get_members_with_role(r, [neon.CustomField.DISCORD_USER]):
                if m.get("Discord User"):
                    print(m["Discord User"], "->", r)
                    role_intent[m["Discord User"]].append(r)

        active_members = []
        for m in neon.get_active_members([neon.CustomField.DISCORD_USER]):
            if m.get("Discord User"):
                active_members.append(m["Discord User"])

        role_intent = dict(role_intent)
        log.info(f"Fetched {len(role_intent)} users' roles in Neon")
        log.info(f"Also {len(active_members)} active members with discord associations")
        print("Role intents:", role_intent)

        if args.apply:
            raise NotImplementedError("TODO APPLY")

        return json.dumps(
            {"role_intent": role_intent, "active_members": active_members}
        )
