"""Commands related operations on Dicsord"""
import logging
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, replace

from dateutil import parser as dateparser

from protohaven_api.config import exec_details_footer
from protohaven_api.integrations import airtable, comms, neon
from protohaven_api.integrations.comms import Msg
from protohaven_api.rbac import Role

log = logging.getLogger("role_automation.roles")


def discord_role_change_dm(logs, discord_id, target=None, intents=None):
    """Generate message for techs about classes with open seats"""
    not_associated = True in ["not associated with a Neon account" in l for l in logs]
    return Msg.tmpl(
        "discord_role_change_dm",
        logs=logs,
        n=len(logs),
        discord_id=discord_id,
        not_associated=not_associated,
        target=target,
        intents=intents,
    )


NOT_ASSOCIATED_TAG = "not_associated"


@dataclass
class DiscordNickIntent:
    """Represents an intent to change the display name of
    a Discord user"""

    discord_id: str = None
    discord_nick: str = None
    action: str = "NICK_CHANGE"


@dataclass
class DiscordIntent:  # pylint: disable=too-many-instance-attributes
    """Represents an intent to change a Discord role"""

    FIELD_MAP = {
        "neon_id": "Neon ID",
        "name": "Name",
        "email": "Email",
        "discord_id": "Discord ID",
        "discord_nick": "Discord Name",
        "action": "Action",
        "role": "Role",
        "state": "State",
        "last_notified": "Last Notified",
    }

    neon_id: str = None
    name: str = None
    email: str = None
    discord_id: str = None
    discord_nick: str = None
    action: str = None
    role: str = None
    rec: str = None
    state: str = None
    last_notified: str = None
    reason: str = None

    def as_key(self):
        """Provide a key for matching like intents based on role, action etc."""
        return f"{self.neon_id}|{self.discord_id}|{self.action}|{self.role}"

    @classmethod
    def from_record(cls, rec):
        """Convert an airtable record to a DiscordIntent"""
        assert rec["fields"]["Action"] in ("ADD", "REVOKE")
        return DiscordIntent(
            **{k: rec["fields"].get(v) for k, v in cls.FIELD_MAP.items()}, rec=rec["id"]
        )

    def to_record(self):
        """Convert an intent to an airtable record's dict data field"""
        data = {
            self.FIELD_MAP[k]: v for k, v in asdict(self).items() if k in self.FIELD_MAP
        }
        if data["Last Notified"]:
            data["Last Notified"] = data["Last Notified"].isoformat()
        return data


SYNC_ROLES = {
    "Onboarders": Role.ONBOARDING["name"],
    "Staff": Role.STAFF["name"],
    "Instructors": Role.INSTRUCTOR["name"],
    "PrivateInstructors": Role.PRIVATE_INSTRUCTOR["name"],
    "Techs": Role.SHOP_TECH["name"],
    "Board": Role.BOARD_MEMBER["name"],
    "TechLeads": Role.SHOP_TECH_LEAD["name"],
    "EduLeads": Role.EDUCATION_LEAD["name"],
    "Admin": Role.ADMIN["name"],
    "Members": None,
}


def singleton_role_sync(neon_member, neon_roles, discord_roles):
    """Given neon membership state and listed roles, compute ops to make discord role smatch"""
    # Remove generic roles not enforced
    discord_roles = discord_roles - {"@everyone"}
    if neon_member != "ACTIVE":
        # Revoke all roles of any users missing Neon information
        if len(discord_roles) == 0:
            return
        for role in discord_roles:
            if neon_member == "NOT_FOUND":
                yield "REVOKE", role, "not associated with a Neon account"
            else:
                yield "REVOKE", role, "membership is inactive"
    else:
        neon_roles.add("Members")  # We're a member
        # Match remaining roles against Neon API server roles
        for to_remove in discord_roles - neon_roles:
            yield "REVOKE", to_remove, "not indicated by Neon CRM"

        for to_add in neon_roles - discord_roles:
            yield "ADD", to_add, "indicated by Neon CRM"


def gen_role_intents(
    user_filter, exclude_users, destructive, max_user_intents
):  # pylint: disable=too-many-locals
    """Generate all intents based on data from discord and neon"""
    state = defaultdict(lambda: [[], None])  # map discord ID to Neon data & roles
    log.info("Fetching all active members")
    rev_roles = {v: k for k, v in SYNC_ROLES.items()}
    for m in neon.get_active_members(
        [
            neon.CustomField.DISCORD_USER,
            neon.CustomField.API_SERVER_ROLE,
            "Account Current Membership Status",
            "Email 1",
            "First Name",
            "Last Name",
        ]
    ):
        sys.stderr.write(".")
        sys.stderr.flush()
        discord_user = (m.get("Discord User") or "").strip()
        roles = {}
        if m.get("API server role"):
            roles = {rev_roles.get(r) for r in m["API server role"].split("|")}
        if discord_user != "":
            state[discord_user][0] = roles
            state[discord_user][1] = m
    sys.stderr.write("\n")
    log.info(
        f"Got {len(state)} total Neon members (with active membership & Discord association)"
    )
    log.debug(f"Discord users: {', '.join(state.keys())}")

    # Here we sort members by join date to have predictable behavior when constrained by
    # max_user_intents. New members joining the server will be affected last.
    # Note that in certain cases, joined_at can be None
    # (see https://discordpy.readthedocs.io/en/stable/api.html#discord.Member.joined_at)
    log.info("Fetch Discord members")
    discord_members, _ = comms.get_all_members_and_roles()
    log.info(f"Got {len(discord_members)}; example {discord_members[0]}")
    discord_members.sort(key=lambda m: m[2])
    modified_users = set()  # for early cutoff on `max_user_intents`

    if user_filter is not None:
        log.warning(f"Filtering to provided user list: {user_filter}")
    if exclude_users is not None:
        log.warning(f"Ignoring excluded users: {exclude_users}")
    for discord_id, nickname, _, assigned_roles in discord_members:
        if exclude_users and discord_id in exclude_users:
            log.debug(f"Skipping {discord_id} (excluded)")
            continue  # Don't enforce ourselves
        if user_filter and discord_id not in user_filter:
            log.debug(f"Skipping {discord_id} (not in filter)")
            continue
        intent = DiscordIntent(discord_id=discord_id, discord_nick=nickname)
        neon_roles, neon_data = state.get(discord_id, (None, None))
        if neon_data:
            intent.neon_id = neon_data["Account ID"]
            intent.name = neon_data["First Name"] + " " + neon_data["Last Name"]
            intent.email = neon_data["Email 1"]
        neon_member = (
            neon_data["Account Current Membership Status"].upper()
            if neon_data
            else "NOT_FOUND"
        )
        neon_roleset = set(neon_roles) if neon_roles else set()

        discord_roleset = {r for r, _ in assigned_roles if r in SYNC_ROLES}
        for action, role, reason in singleton_role_sync(
            neon_member, neon_roleset, discord_roleset
        ):
            if action == "REVOKE" and not destructive:
                log.debug(
                    f"Omitting destructive action {action} {role} ({reason}) for {intent}"
                )
                continue
            modified_users.add(discord_id)
            if len(modified_users) > max_user_intents:
                break
            yield replace(intent, action=action, role=role, reason=reason)


def handle_delayed_revocation(
    vi, va, now, user_log, apply_records, apply_discord
):  # pylint: disable=too-many-arguments
    """Update airtable and apply role revocations based on elapsed time after comms"""
    # Removals are given 14 days' notice, then again within at least 24 hours.
    # If we haven't sent a notification, make sure one gets sent out
    if va.last_notified is None:
        prefix = "IN 14 DAYS" if va.state == "first_warning" else "IN 24 HOURS"
        user_log[va.discord_id].append(
            (
                f"{prefix}: {va.action.lower()} Discord role {va.role} ({vi.reason})",
                va.rec,
            )
        )
        return None

    notified_days_ago = (now - dateparser.parse(va.last_notified)).days
    if va.state == "first_warning" and notified_days_ago > 13:
        user_log[vi.discord_id].append(
            (f"IN 24 HOURS - revoke Discord role {vi.role} ({vi.reason})", va.rec)
        )
        if apply_records:
            status, content = airtable.update_record(
                replace(va, state="final_warning", last_notified=None).to_record(),
                "people",
                "automation_intents",
                va.rec,
            )
            if status != 200:
                log.error(f"Error {status} updating record {va}: {content}")
    elif va.state == "final_warning" and notified_days_ago > 0:
        user_log[vi.discord_id].append(
            (f"Revoked Discord role {vi.role} ({vi.reason})", None)
        )
        if apply_discord:
            rep = comms.revoke_discord_role(vi.discord_id, vi.role)
            if rep is not True:
                log.error(f"Error removing role {vi.role} from {vi.discord_id}: {rep}")
            else:
                if apply_records:
                    status, content = airtable.delete_record(
                        "people", "automation_intents", va.rec
                    )
                    if status != 200:
                        log.error(f"Error {status} deleting record {va.rec}: {content}")
                return True
    return None


def handle_role_addition(v, user_log, apply_discord=True):
    """Fulfill the role addition"""
    assert v.action == "ADD"
    user_log[v.discord_id].append(
        (f"Discord role assigned: {v.role} ({v.reason})", None)
    )
    if not apply_discord:
        return True  # Fake it

    rep = comms.set_discord_role(v.discord_id, v.role)
    if rep is not True:
        log.error(f"Error adding role {v.role} to {v.discord_id}: {rep}")
    return rep


def sync_delayed_intents(intents, airtable_intents, user_log, apply_records):
    """Add and delete intents based on generated list"""
    for k in set(intents.keys()).union(set(airtable_intents.keys())):
        intent = intents.get(k, airtable_intents.get(k))
        status, content = 200, None
        prefix = None
        if (
            k not in airtable_intents
            and intent.rec is None
            and intent.action == "REVOKE"
        ):
            prefix = "IN 14 DAYS"
            if apply_records:
                status, content = airtable.insert_records(
                    [replace(intent, state="first_warning").to_record()],
                    "people",
                    "automation_intents",
                )
                if status != 200:
                    log.error(content)
                else:
                    intent.rec = content["records"][0]["id"]
            else:
                # Don't stage impending comms if we aren't inserting the record
                log.warning(
                    f"Skip record insertion: {intent.discord_id} {prefix} "
                    f"{intent.action.lower()} Discord role {intent.role} ({intent.reason})"
                )
                continue
        elif k not in intents and intent.rec is not None:
            prefix = "CANCELED"
            intent.reason = "Now present in Neon CRM"
            if apply_records:
                status, content = airtable.delete_record(
                    "people", "automation_intents", intent.rec
                )
            else:
                # Don't stage cancellation comms if we don't update the record
                log.warning(
                    f"Skip record deletion: {intent.discord_id} {prefix} "
                    f"{intent.action.lower()} Discord role {intent.role} ({intent.reason})"
                )
                continue

        if prefix:
            user_log[intent.discord_id].append(
                (
                    f"{prefix}: {intent.action.lower()} Discord role "
                    f"{intent.role} ({intent.reason})",
                    intent.rec,
                )
            )
            if status != 200:
                log.error(content)


def gen_role_comms(user_log, roles_assigned, roles_revoked):
    """Generates individual DMs and summary message based on actions taken"""
    for discord_id, logs in user_log.items():
        lines, recs = zip(*logs)
        yield discord_role_change_dm(
            lines,
            discord_id,
            target=f"@{discord_id}",
            intents=[r for r in recs if r is not None],
        )

    if len(user_log) > 0:
        yield Msg.tmpl(
            "discord_role_change_summary",
            users=list(user_log.keys()),
            n=len(user_log),
            roles_assigned=roles_assigned,
            roles_revoked=roles_revoked,
            footer=exec_details_footer(),
            target="#membership-automation",
        )


def resolve_nickname(first, preferred, last, pronouns):
    """Convert neon values into a single string of Discord nickname for user"""
    first = first.strip() if first else ""
    preferred = preferred.strip() if preferred else ""
    last = last.strip() if last else ""
    pronouns = pronouns.strip() if pronouns else ""
    first = preferred if preferred != "" else first
    nick = f"{first} {last}".strip() if first != last else first
    if pronouns != "":
        nick += f" ({pronouns})"
    return nick


def setup_discord_user(discord_details):  # pylint: disable=too-many-locals
    """Given a user's discord ID and roles, carry out initial association
    and role assignment. While the periodic discord automation will
    handle this eventually, setup_user greatly
    shortens the lead time for a new member joining discord and seeing
    member channels.

    Note that we do blocking calls on async DiscordBot functions in `comms`,
    but this function may be called by the bot itself (causing deadlock).
    This is why we yield named function calls back to the caller to handle as
    needed.
    """
    discord_id, display_name, _, discord_roles = discord_details
    discord_roles = {dd[0] for dd in discord_roles}
    # Now we need to fetch the neon roles and membership state.
    # At this point we may bail out and ask them to associate.
    rev_roles = {v: k for k, v in SYNC_ROLES.items()}
    log.info("Searching for discord user in Neon")
    mm = list(
        neon.get_members_with_discord_id(
            discord_id,
            extra_fields=[
                "Preferred Name",
                neon.CustomField.PRONOUNS,
                neon.CustomField.API_SERVER_ROLE,
                "Account Current Membership Status",
            ],
        )
    )
    log.info(mm)
    if len(mm) == 0:
        log.info("Neon user not found; issuing association request")
        msg = Msg.tmpl("not_associated", target=f"@{discord_id}", discord_id=discord_id)
        yield "send_dm", discord_id, f"**{msg.subject}**\n\n{msg.body}"
        airtable.log_comms(NOT_ASSOCIATED_TAG, f"@{discord_id}", msg.subject, "Sent")
        return

    m = mm[0]
    neon_member = None
    neon_roles = set()
    for m in mm:
        neon_roles = neon_roles.union(
            {
                rev_roles.get(r)
                for r in (m.get("API server role") or "").split("|")
                if r.strip() != ""
            }
        )
        if neon_member != "ACTIVE":
            neon_member = m["Account Current Membership Status"].upper()
    log.info(f"Found matching Neon account {m['Account ID']}, status {neon_member}")

    # Sync display/nickname
    nick = resolve_nickname(
        m.get("First Name"),
        m.get("Preferred Name"),
        m.get("Last Name"),
        m.get("Pronouns"),
    )
    if nick != display_name:
        log.info(f"{discord_id} display name: {display_name} -> {nick}")
        yield "set_nickname", discord_id, nick

    # Go through intents and apply any that are additive.
    log.info(f"singleton_role_sync({neon_member}, {neon_roles}, {discord_roles})")
    user_log = []
    for action, role, reason in singleton_role_sync(
        neon_member, neon_roles, discord_roles
    ):
        if action != "ADD":
            log.info(f"Deferring action {action} on role {role} (reason {reason})")
            continue
        yield "grant_role", discord_id, role
        user_log.append(f"Discord role assigned: {role} ({reason})")

    if len(user_log) > 0:
        msg = discord_role_change_dm(user_log, discord_id)
        yield "send_dm", discord_id, f"**{msg.subject}**\n\n{msg.body}"
    log.info("setup_discord_user done")


def setup_discord_user_sync(discord_id):
    """Synchronous version of `setup_discord_user`. Must be called outside of
    discord bot / coroutine flow to prevent deadlock"""
    details = comms.get_member_details(discord_id)
    if details is None:
        return False
    for a in setup_discord_user(details):
        if a[0] == "send_dm":
            comms.send_discord_message(a[2], f"@{a[1]}")
        elif a[0] == "set_nickname":
            comms.set_discord_nickname(a[1], a[2])
        elif a[0] == "grant_role":
            comms.set_discord_role(a[1], a[2])
        else:
            raise RuntimeError(f"Unhandled uesr sync action: {a}")
    return True
