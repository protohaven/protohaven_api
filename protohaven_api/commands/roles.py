"""Commands related operations on Dicsord"""
import argparse
import logging
from collections import defaultdict

import yaml

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, comms, neon
from protohaven_api.role_automation import roles

log = logging.getLogger("cli.roles")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for managing roles of members"""

    @command(
        arg(
            "--apply_records",
            help="when true, Airtable is updated with state of intents",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--apply_discord",
            help="when true, Discord roles are updated",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--filter",
            help="Restrict to comma separated list of discord users",
            type=str,
        ),
        arg(
            "--exclude",
            help="Don't process this comma separated list of discord users",
            type=str,
        ),
        arg(
            "--max_users_affected",
            help="Only allow at most this number of users to receive role changes",
            type=int,
            default=10,
        ),
        arg(
            "--destructive",
            help="Stage and execute destructive changes",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def update_role_intents(self, args):  # pylint: disable=too-many-locals
        """Syncs the roles in discord with the state of membership and custom fields in Neon.
        Role revocations are delayed and users DM'd in advance of the change, so they
        have time to remedy the cause of the revocation.
        """
        if not args.apply_discord:
            log.warning(
                "***** --apply_discord not set; roles will not actually change *****"
            )
        if not args.apply_records:
            log.warning("***** --apply_records not set; airtable will not update *****")
        log.info("Fetching role intents from Neon and Discord")
        user_filter = set(args.filter.split(",")) if args.filter else None
        exclude_users = set(args.exclude.split(",")) if args.exclude else None
        intents = {
            i.as_key(): i
            for i in roles.gen_role_intents(
                user_filter, exclude_users, args.destructive, args.max_users_affected
            )
        }
        log.info(f"Fetched {len(intents)} intents")

        log.info("Fetching pending intents from Airtable")
        airtable_intents = {}
        for rec in airtable.get_role_intents():
            i = roles.DiscordIntent.from_record(rec)
            log.debug(str(i))
            airtable_intents[i.as_key()] = i
        log.info(f"Fetched {len(airtable_intents)} intents")

        user_log = defaultdict(list)  # Log of actions taken, keyed by discord_id

        log.info("Syncing delayed intents (insert/delete)")
        roles.sync_delayed_intents(
            intents, airtable_intents, user_log, apply_records=args.apply_records
        )

        # Handle all additions
        roles_assigned = 0
        log.info("Handling role additions")
        for i, v in enumerate(intents.values()):
            if v.action != "ADD":
                continue
            if roles.handle_role_addition(
                v, user_log, apply_discord=args.apply_discord
            ):
                roles_assigned += 1

        now = tznow()
        roles_revoked = 0
        log.info("Handling delayed revocations")
        for k in set(intents.keys()).intersection(set(airtable_intents.keys())):
            vi = intents[k]
            if vi.action != "REVOKE":
                continue
            va = airtable_intents[k]
            if roles.handle_delayed_revocation(
                vi,
                va,
                now,
                user_log,
                apply_records=args.apply_records,
                apply_discord=args.apply_discord,
            ):
                roles_revoked += 1

        result = list(roles.gen_role_comms(user_log, roles_assigned, roles_revoked))
        print(
            yaml.dump(
                result,
                default_flow_style=False,
                default_style="",
            )
        )
        log.info(f"Done - generated {len(result)} comms")

    @command(
        arg(
            "--apply",
            help="Actually make changes to discord user nicknames",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--limit",
            help="Limit number of changes to this amount",
            type=int,
            default=3,
        ),
    )
    def enforce_discord_nicknames(self, args):
        """Ensure nicknames of all associated Discord users are properly set.
        This only targets active members, as inactive members shouldn't
        be present in channels anyways."""
        discord_members, _ = comms.get_all_members_and_roles()
        user_nick = {m[0]: m[1] for m in discord_members}

        if not args.apply:
            log.warning(
                "--apply not set; will only print name changes and not modify Discord"
            )

        i = 0
        for m in neon.get_active_members(
            [
                neon.CustomField.DISCORD_USER,
                neon.CustomField.PRONOUNS,
                "First Name",
                "Last Name",
                "Preferred Name",
            ]
        ):
            if i >= args.limit:
                log.info(f"Limit of {args.limit} changes reached; stopping")
                return
            discord_user = (m.get("Discord User") or "").strip()
            if discord_user == "":
                continue
            first = (
                m["Preferred Name"].strip()
                if "Preferred Name" in m
                else m.get("First Name").strip()
            )
            last = m.get("Last Name").strip()
            nick = f"{first} {last}" if first != last else first
            if m.get("Pronouns"):
                nick += f" ({m['Pronouns']})"
            cur = user_nick.get(discord_user)
            if not cur:
                continue
            if nick != cur:
                log.info(
                    f"Discord user {discord_user} nickname change: {cur} -> {nick}"
                )
                if args.apply:
                    log.info(str(comms.set_discord_nickname(discord_user, nick)))
                    i += 1

    @command(
        arg(
            "neon",
            help="Neon ID",
            type=str,
        ),
        arg(
            "discord",
            help="Discord user",
            type=str,
        ),
    )
    def associate_discord(self, args):
        """Associate a Discord ID with a neon user"""
        print(neon.set_discord_user(args.neon, args.discord))
