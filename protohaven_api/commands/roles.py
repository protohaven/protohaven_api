"""Commands related operations on Dicsord"""

import argparse
import datetime
import logging
import re
from collections import defaultdict

from protohaven_api.automation.roles import roles
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, comms, neon
from protohaven_api.integrations.comms import Msg

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
    def update_role_intents(self, args, _):  # pylint: disable=too-many-locals
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
        for v in intents.values():
            log.info(f"Intent {v}")

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
        print_yaml(result)
        log.info(f"Done - generated {len(result)} comms")

    @command(
        arg(
            "--apply",
            help="Actually make changes to discord user nicknames",
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
            "--warn_not_associated",
            help="Send a DM to all users not associated in Neon",
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
    def enforce_discord_nicknames(
        self, args, _
    ):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """Ensure nicknames of all associated Discord users are properly set.
        This only targets active members, as inactive members shouldn't
        be present in channels anyways."""
        discord_members, _ = comms.get_all_members_and_roles()
        user_nick = {m[0]: m[1] for m in discord_members}
        join_dates = {m[0]: m[2] for m in discord_members}

        if args.filter:
            log.info(f"Applying filter {args.filter}")
            ff = {f.strip() for f in args.filter.split(",")}
            user_nick = {k: v for k, v in user_nick.items() if k in ff}
        if args.exclude:
            log.info(f"Applying exclusions {args.exclude}")
            ee = {e.strip() for e in args.exclude.split(",")}
            user_nick = {k: v for k, v in user_nick.items() if k not in ee}

        if not args.apply:
            log.warning(
                "--apply not set; will only print name changes and not modify Discord"
            )

        i = 0
        result = []
        changes = []
        not_associated = set(user_nick.keys())
        for m in neon.get_all_accounts_with_discord_association(
            [
                neon.CustomField.DISCORD_USER,
                neon.CustomField.PRONOUNS,
                "First Name",
                "Last Name",
                "Preferred Name",
            ]
        ):
            discord_id = (m.get("Discord User") or "").strip()
            if discord_id == "":
                continue
            if (
                discord_id in not_associated
            ):  # Not all associated users remain in Discord
                not_associated.remove(discord_id)

            if i == args.limit:
                log.info(f"Limit of {args.limit} changes reached")
                i += 1
            elif i < args.limit:
                nick = roles.resolve_nickname(
                    m.get("First Name"),
                    m.get("Preferred Name"),
                    m.get("Last Name"),
                    m.get("Pronouns"),
                )
                cur = user_nick.get(discord_id)
                if not cur:
                    continue
                if nick != cur:
                    changes.append(
                        f"{discord_id} ({cur} -> {nick}){' (dry run)' if not args.apply else ''}"
                    )
                    log.info(changes[-1])
                    if args.apply:
                        log.info(str(comms.set_discord_nickname(discord_id, nick)))
                    i += 1
                    result.append(
                        Msg.tmpl(
                            "discord_nick_changed",
                            prev_nick=cur,
                            next_nick=nick,
                            target=f"@{discord_id}",
                            id=f"{discord_id}_nick_change",
                        )
                    )

        not_associated_final = []
        i = 0
        if args.warn_not_associated:
            thresh = tznow() - datetime.timedelta(days=30)
            notification_cache = {
                k.replace("@", "")
                for k, v in airtable.get_notifications_after(
                    re.compile(r"^not_associated.*"), after_date=thresh
                ).items()
            }
            log.info(
                f"Crawling {len(not_associated)} unassociated discord users, "
                "starting with most recent to join"
            )
            not_associated = list(not_associated)
            not_associated.sort(key=join_dates.get, reverse=True)
            for discord_id in not_associated:
                if i >= args.limit:
                    log.info("Limit reached; stopping early")
                    break
                if discord_id in notification_cache:
                    log.info(
                        f"Skipping association reminder for {discord_id} "
                        "(already notified in last 30 days)"
                    )
                    continue
                not_associated_final.append(discord_id)
                result.append(
                    Msg.tmpl(
                        "not_associated",
                        discord_id=discord_id,
                        target=f"@{discord_id}",
                        id=roles.NOT_ASSOCIATED_TAG,
                    )
                )
                i += 1

        if len(changes) > 0 or (
            len(not_associated_final) > 0 and args.warn_not_associated
        ):
            m = len(not_associated_final)
            notified = list(not_associated_final)
            if m > 30:
                notified = notified[:30] + ["..."]
            result.append(
                Msg.tmpl(
                    "discord_nick_change_summary",
                    target="#discord-automation",
                    changes=list(changes),
                    n=len(changes),
                    notified=notified,
                    m=m,
                )
            )

        print_yaml(result)
