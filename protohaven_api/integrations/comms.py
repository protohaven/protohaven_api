"""Discord, email, and potentially other communications

Required, IMAP enabled in gmail, also less secure access turned on
see https://myaccount.google.com/u/3/lesssecureapps
"""

import re

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector


def send_email(subject, body, recipients):
    """Sends an email via GMail API"""
    return get_connector().email(subject, body, recipients)


def send_discord_message(content, channel=None, blocking=True):
    """Sends a message to the techs-live channel"""
    cfg = get_config()["comms"]
    if channel is None:
        channel = cfg["techs-live"]
    elif channel.startswith("@"):  # Send to a user
        return get_connector().discord_bot_send_dm(channel[1:], content)
    elif channel.startswith("#"):  # Send to a channel
        channel = cfg[channel[1:]]
    else:
        raise RuntimeError(f"Unknown channel '{channel}' for discord message")

    # For convenience, any recognizable @role mentions are converted
    # See https://discord.com/developers/docs/reference#message-formatting
    def sub_roles(m):
        s = m.group()
        role_id = cfg["discord_roles"].get(m.group()[1:], None)
        if role_id is None:
            return s

        print(f"Replacing {s} with role id tag {role_id}")
        return f"<@&{role_id}>"

    content = re.sub(r"@\w+", sub_roles, content, flags=re.MULTILINE)

    result = get_connector().discord_webhook(channel, content)
    if blocking:
        result.raise_for_status()
    else:
        return result


def send_help_wanted(content):
    """Sends a message to the help-wanted channel"""
    return send_discord_message(content, "#help-wanted")


def send_board_message(content):
    """Sends a message to the board-private channel"""
    return send_discord_message(content, "#board-private")


def send_membership_automation_message(content):
    """Sends message to membership automation channel.
    Messages are sent asynchronously and not awaited"""
    return send_discord_message(content, "#membership-automation", blocking=False)


def set_discord_nickname(name, nick):
    """Sets the nickname of a discord user"""
    return get_connector().discord_bot_setnick(name, nick)


def set_discord_role(name, role):
    """Adds a role for a discord user, e.g. Members"""
    return get_connector().discord_bot_setrole(name, role)


def revoke_discord_role(name, role):
    """Removes a role for a discord user"""
    return get_connector().discord_bot_revoke_role(name, role)


def get_all_members_and_roles():
    """Gets all members and roles on Discord"""
    return get_connector().discord_bot_get_all_members_and_roles()
