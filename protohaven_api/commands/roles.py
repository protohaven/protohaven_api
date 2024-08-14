"""Commands related operations on Dicsord"""
import argparse
import json
import logging
import sys
import yaml
from collections import defaultdict
from enum import Enum
from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command
from protohaven_api.integrations import airtable, neon, comms
from protohaven_api.commands import comms as ccom
from protohaven_api.config import tznow
from protohaven_api.rbac import Role
from enum import Enum
from collections import namedtuple
log = logging.getLogger("cli.roles")


DiscordIntent = namedtuple("DiscordIntent", "neon_id,name,email,discord_id,discord_nick,action,role,rec,state,last_notified,reason", defaults=[None for _ in range(11)])
DiscordIntent.as_key = lambda s: f"{s.neon_id}|{s.discord_id}|{s.action}|{s.role}"
field_map = {
        'neon_id': 'Neon ID',
        'name': 'Name',
        'email': 'Email',
        'discord_id': 'Discord ID',
        'discord_nick': 'Discord Name',
        'action': 'Action',
        'role': 'Role',
        'state': 'State',
        'last_notified': 'Last Notified',
        }
def intent_from_record(rec):
    assert rec['fields']['Action'] in ("ADD", "REVOKE")
    return DiscordIntent(**{k: rec['fields'].get(v) for k,v in field_map.items()}, rec=rec['id'])
def intent_to_record_data(intent):
    data = {field_map[k]: v for k, v in intent._asdict().items() if k in field_map}
    if data['Last Notified']:
        data['Last Notified'] = data['Last Notified'].isoformat()
    return data


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for managing roles of members"""

    SYNC_ROLES = {
        "Onboarders": Role.ONBOARDING['name'],
        "Staff": Role.STAFF['name'],
        "Instructors": Role.INSTRUCTOR['name'],
        "Techs": Role.SHOP_TECH['name'],
        "Board": Role.BOARD_MEMBER['name'],
        "TechLeads": Role.SHOP_TECH_LEAD['name'],
        "Admin": Role.ADMIN['name'],
        "Members": None,
    }

    def singleton_role_sync(self, neon_member, discord_member, neon_roles, discord_roles):
        # Revoke all roles of any users missing Neon information
        if neon_member != "ACTIVE":
            if len(discord_roles) == 0 and not discord_member:
                return
            for role in discord_roles:
                yield "REVOKE", role, "not associated with a Neon account" if neon_member == "NOT_FOUND" else "membership is inactive"
        else:
            neon_roles.add("Members") # We're a member
            # Match remaining roles against Neon API server roles
            for to_remove in (discord_roles - neon_roles):
                yield "REVOKE", to_remove, "not indicated by Neon CRM"
            
            for to_add in (neon_roles - discord_roles):
                yield "ADD", to_add, "indicated by Neon CRM"


    def gen_role_intents(self, user_filter, exclude_users, destructive, max_user_intents):
        state = defaultdict(lambda: [[], None])  # map discord ID to Neon data & roles
        log.info(f"Fetching all active members")
        rev_roles = {v:k for k,v in self.SYNC_ROLES.items()}
        for m in neon.get_active_members([neon.CustomField.DISCORD_USER, neon.CustomField.API_SERVER_ROLE, "Account Current Membership Status", "Email 1", "First Name", "Last Name"]):
            sys.stderr.write(".")
            sys.stderr.flush()
            discord_user = (m.get("Discord User") or "").strip()
            roles = {}
            if m['API server role']:
                roles = {rev_roles.get(r) for r in m['API server role'].split('|')}
            if discord_user != "":
                state[discord_user][0] = roles
                state[discord_user][1] = m
        sys.stderr.write("\n")
        log.info(f"Got {len(state)} total Neon members (with active membership & Discord association)")
        log.debug(f"Discord users: {', '.join(state.keys())}")

        # Here we sort members by join date to have predictable behavior when constrained by
        # max_user_intents. New members joining the server will be affected last.
        # Note that in certain cases, joined_at can be None
        # (see https://discordpy.readthedocs.io/en/stable/api.html#discord.Member.joined_at)
        log.info("Fetch Discord members")
        discord_members, _ = comms.get_all_members_and_roles()
        log.info(f"Got {len(discord_members)}; example {discord_members[0]}")
        discord_members.sort(key=lambda m: m[2])

        discord_member_map = {discord_id: (nickname, roles) for discord_id, nickname, joined_at, roles in discord_members}
        modified_users = set()

        if user_filter is not None:
            log.warning(f"Filtering to provided user list: {user_filter}")
        if exclude_users is not None:
            log.warning(f"Ignoring excluded users: {exclude_users}")
        for discord_id, nickname, joined_at, assigned_roles in discord_members:
            if discord_id in exclude_users:
                log.debug(f"Skipping {discord_id} (excluded)")
                continue # Don't enforce ourselves
            if user_filter and discord_id not in user_filter:
                log.debug(f"Skipping {discord_id} (not in filter)")
                continue
            intent = DiscordIntent(discord_id=discord_id, discord_nick=nickname)
            neon_roles, neon_data = state.get(discord_id, (None, None))
            if neon_data:
                intent = intent._replace(neon_id = neon_data['Account ID'], 
                                         name = neon_data['First Name'] + " " + neon_data['Last Name'],
                                         email = neon_data['Email 1'])
            neon_member = (neon_data['Account Current Membership Status'].upper() if neon_data else "NOT_FOUND")
            neon_roleset = set(neon_roles) if neon_roles else set()
            
            discord_member = "Members" in {name for name, id in assigned_roles}
            discord_roleset = {r for r, _ in assigned_roles if r in self.SYNC_ROLES or r == "Members"}
            # log.debug(f"singleton role sync for {discord_id}: {neon_member}, {discord_member}, {neon_roleset}, {discord_roleset}")
            for action, role, reason in self.singleton_role_sync(neon_member, discord_member, neon_roleset, discord_roleset):
                if action == "REVOKE" and not destructive:
                    log.warning(f"Omitting destructive action {action} {role} ({reason}) for {intent}")
                    continue
                modified_users.add(discord_id)
                if len(modified_users) > max_user_intents:
                    break
                yield intent._replace(action=action, role=role, reason=reason)


    def handle_delayed_revocation(self, vi, va, now, user_log, apply_records, apply_discord):
        # Removals are given 14 days' notice, then again within at least 24 hours.
        # If we haven't sent a notification, make sure one gets sent out
        if va.last_notified is None:
            prefix = "IN 14 DAYS" if va.state == "first_warning" else "IN 24 HOURS"
            user_log[va.discord_id].append((f"{prefix}: {va.action.lower()} Discord role {va.role} ({vi.reason})", va.rec))
            return

        notified_days_ago = (now - dateparser.parse(va.last_notified)).days
        if va.state == "first_warning" and notified_days_ago > 13:
            user_log[vi.discord_id].append((f"IN 24 HOURS - revoke Discord role {vi.role} ({vi.reason})", va.rec))
            if apply_records:
                status, content = airtable.update_record(intent_to_record_data(va._replace(state="final_warning", last_notified=None)), "people", "automation_intents", va.rec)
                if status != 200:
                    log.error(f"Error {status} updating record {va}: {content}")
        elif va.state == "final_warning" and notified_days_ago > 0:
            user_log[vi.discord_id].append((f"Revoked Discord role {vi.role} ({vi.reason})", None))
            if apply_discord:
                rep = comms.revoke_discord_role(vi.discord_id, vi.role)
                if rep is not True:
                    log.error(f"Error removing role {v.role} from {vi.discord_id}: {rep}")
                else:
                    if apply_records:
                        status, content = airtable.delete_record("people", "automation_intents", va.rec)
                        if status != 200:
                            log.error(f"Error {status} deleting record {rec}: {content}")
                    return True
            else:
                log.warning(f"Skipped revoking role {vi.role} from {vi.discord_id} (--apply_discord not set)")

    def handle_role_addition(self, v, user_log, apply_discord):
        # Go through any role additions and fulfill them
        user_log[v.discord_id].append((f"Discord role assigned: {v.role} ({v.reason})", None))
        if not apply_discord:
            log.warning(f"Skipped adding role {vi.role} to {vi.discord_id} (--apply_discord not set)")
            return True # Fake it

        rep = comms.set_discord_role(v.discord_id, v.role)
        if rep is not True:
            log.error(f"Error adding role {v.role} to {v.discord_id}: {rep}")
        return rep

    def sync_delayed_intents(self, intents, airtable_intents, user_log, apply_records):
        """Add and delete intents based on generated list"""
        for k in set(intents.keys()).union(set(airtable_intents.keys())):
            intent = intents.get(k, airtable_intents.get(k))
            status, content = 200, None
            prefix = None
            if k not in airtable_intents and intent.rec is None and intent.action == "REVOKE":
                prefix = "IN 14 DAYS"
                if apply_records:
                    status, content = airtable.insert_records([intent_to_record_data(intent._replace(state="first_warning"))], "people", "automation_intents")
                    if status != 200:
                        log.error(content)
                    else:
                        intent = intent._replace(rec=content['records'][0]['id'])
            elif k not in intents and intent.rec is not None:
                prefix = "CANCELLED"
                intent = intent._replace(reason="Now present in Neon CRM")
                if apply_records:
                    status, content = airtable.delete_record("people", "automation_intents", intent.rec)

            if prefix:
                user_log[intent.discord_id].append((f"{prefix}: {intent.action.lower()} Discord role {intent.role} ({intent.reason})", intent.rec))
                if status != 200:
                    log.error(content)

    def gen_role_comms(self, user_log, roles_assigned, roles_revoked):
        for discord_id, logs in user_log.items():
            lines, recs = zip(*logs)
            subject, body = ccom.discord_role_change_dm(lines, discord_id)
            yield {
                    "target": f"@{discord_id}",
                    "subject": subject,
                    "body": body,
                    "intents": [r for r in recs if r is not None],
                }

        if len(user_log) > 0:
            subject, body = ccom.discord_role_change_summary(user_log, roles_assigned, roles_revoked) 
            yield {
                    "target": "#membership-automation",
                    "subject": subject, 
                    "body": body,
                }
                    
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
    def update_role_intents(self, args):
        """Syncs the roles in discord with the state of membership and custom fields in Neon.
            Role revocations are delayed and users DM'd in advance of the change, so they
            have time to remedy the cause of the revocation.
        """
        log.info("Fetching role intents from Neon and Discord")
        user_filter = set(args.filter.split(',')) if args.filter else None
        exclude_users = set(args.exclude.split(',')) if args.exclude else None
        intents = {i.as_key(): i for i in self.gen_role_intents(user_filter, exclude_users, args.destructive, args.max_users_affected)}
        log.info(f"Fetched {len(intents)} intents")

        log.info("Fetching pending intents from Airtable")
        airtable_intents = {}
        for rec in airtable.get_role_intents():
            i = intent_from_record(rec)
            log.debug(str(i))
            airtable_intents[i.as_key()] = i
        log.info(f"Fetched {len(airtable_intents)} intents")
    
        user_log = defaultdict(list) # Log of actions taken, keyed by discord_id

        log.info("Syncing delayed intents (insert/delete)")
        self.sync_delayed_intents(intents, airtable_intents, user_log, apply_records=args.apply_records)

        # Handle all additions
        roles_assigned = 0
        log.info("Handling role additions")
        for i, v in enumerate(intents.values()):
            if v.action != "ADD":
                continue
            if self.handle_role_addition(v, user_log, apply_discord=args.apply_discord):
                roles_assigned += 1

        now = tznow()
        roles_revoked = 0
        log.info("Handling delayed revocations")
        for k in set(intents.keys()).intersection(set(airtable_intents.keys())):
            vi = intents[k]
            if vi.action != "REVOKE":
                continue
            va = airtable_intents[k]
            if self.handle_delayed_revocation(vi, va, now, user_log, apply_records=args.apply_records, apply_discord=args.apply_discord):
                roles_revoked += 1

        
        print(yaml.dump(list(self.gen_role_comms(user_log, roles_assigned, roles_revoked)), default_flow_style=False, default_style=""))


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
        print(neon.set_discord_user(args.neon, args.discord))
