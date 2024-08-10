"""Commands related operations on Dicsord"""
import argparse
import json
import logging
import sys
from collections import defaultdict
from enum import Enum

from protohaven_api.commands.decorator import arg, command
from protohaven_api.integrations import neon, comms  # pylint: disable=import-error
from protohaven_api.rbac import Role
from enum import Enum
from collections import namedtuple
log = logging.getLogger("cli.roles")

class Action(Enum):
    REVOKE_ALL = 1
    REVOKE = 3
    ADD_MEMBER = 4
    ADD = 5



DiscordIntent = namedtuple("DiscordIntent", "neon_id,name,email,discord_id,discord_nick,action,role,rec,state,last_notified", defaults=[None for _ in range(7)])
DiscordIntent.as_key = lambda self: f"{neon_id}|{discord_id}|{action}|{role}"
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
    return DiscordIntent(**{k: rec['fields'].get(v) for k,v in field_map.items(), 'rec': rec['id']})

class Commands:  # pylint: disable=too-few-public-methods
    """Commands for managing roles of members"""

    SYNC_ROLES = {
        "Onboarders": Role.ONBOARDING,
        "Staff": Role.STAFF,
        "Instructors": Role.INSTRUCTOR,
        "Techs": Role.SHOP_TECH,
        "Board": Role.BOARD_MEMBER,
        "TechLeads": Role.SHOP_TECH_LEAD,
        "Admin": Role.ADMIN,
    }

    def singleton_role_sync(self, neon_member, discord_member, neon_roles, discord_roles):
        # Revoke all roles of any users missing Neon information
        if not neon_member:
            if len(discord_roles) == 0 and not discord_member:
                return
            yield Action.REVOKE_ALL, None
        else:
            if not discord_member:
                yield Action.ADD_MEMBER, None

            # Match remaining roles against Neon API server roles
            for to_remove in (discord_roles - neon_roles):
                yield Action.REVOKE, to_remove
            
            for to_add in (neon_roles - discord_roles):
                yield Action.ADD, to_add


    def compute_role_assignment_intent(self):
        state = defaultdict(lambda: [[], None])  # map discord ID to Neon data & roles
        for r in self.SYNC_ROLES.values():
            if r is None:
                continue
            for m in neon.get_members_with_role(r, [neon.CustomField.DISCORD_USER, "Account Current Membership Status", "Email 1"]):
                sys.stderr.write(".")
                sys.stderr.flush()
                if m.get("Discord User"):
                    state[m["Discord User"]][0].append(r)
                    state[m["Discord User"]][1] = m

        discord_members, _ = comms.get_all_members_and_roles()
        discord_member_map = {discord_id: (nickname, roles) for discord_id, nickname, roles in discord_members}
        for discord_id, nickname, assigned_roles in discord_members:
            intent = DiscordIntent(discord_id=discord_id, discord_nick=nickname)
            neon_roles, neon_data = state.get(discord_id, (None, None))
            if neon_data:
                intent = intent._replace(neon_id = neon_data['Account ID'], 
                                         name = neon_data['First Name'] + " " + neon_data['Last Name'],
                                         email = neon_data['Email 1'])
            neon_member = (neon_data['Account Current Membership Status'] == "ACTIVE") if neon_data else False
            neon_roleset = {r['name'] for r in neon_roles} if neon_roles else {}
            
            discord_member = "Members" in {name for name, id in assigned_roles}
            discord_roleset = set()
            for role_name, _ in assigned_roles:
                r = self.SYNC_ROLES.get(role_name)
                if r is not None:
                    discord_roleset.add(r['name'])

            for action, role in self.singleton_role_sync(neon_member, discord_member, neon_roleset, discord_roleset):
                yield intent._replace(action=action, role=role)


    @command(
        arg(
            "--apply",
            help="when true, Airtable is updated with state of intents",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def update_role_intents(self, args):
        """Syncs the roles in discord with the state of membership and custom fields in Neon
        WARNING: WORK IN PROGRESS
        """
        log.info("Fetching role intents from Neon and Discord")
        intents = {i.as_key(): i for i in self.compute_role_assignment_intent()}
        log.info(f"Fetched {len(intents)} intents")

        log.info("Fetching pending intents from Airtable")
        airtable_intents = {}
        for rec in airtable.get_role_intents():
            i = intent_from_record(rec)
            airtable_intents[i.as_key()] = i
        log.info("Fetched {len(airtable_intents)} intents")
    
        if args.apply:
            raise NotImplementedError("TODO APPLY")
        log.info("Done")

        # Remove any intents in airtable that aren't computed this pass
        to_delete = [ airtable_intents[k].rec for k in set(airtable_intents.keys()) - set(intents.keys()) ]
        to_add = [ intents[k]._replace(state="first_warning") for k in set(intents.keys()) - set(airtable_intents.keys()) ]
        to_update = []

        to_act = defaultdict(list)
        for v in intents.values():
            if v.action in (Action.ADD, Action.ADD_MEMBER):
                to_act[v.discord_id].append(v)

        now = tznow()
        for k in set(intents.keys()).intersection(set(airtable_intents.keys())):
            vi = intents[k]
            va = airtable_intents[k]

            # Removals are given 14 days' notice, then again within at least 24 hours
            if va.last_notified:
                notified_days_ago = (now - dateparser.parse(va.last_notified)).days
                if va.state == "first_warning" and notified_days_ago > 13:
                    to_update.append(va._replace(state="final_warning", last_notified=None))
                    continue
                elif va.state == "final_warning" and notified_days_ago > 0:
                    to_act[va.discord_id].append(va)

        # Perform actions, adding deletions as needed
        for discord_id, v in to_act.items():
            raise RuntimeError("TODO")
            
        

        print(yaml.dump(result, default_flow_style=False, default_style=""))
