"""Discord, email, and potentially other communications

Required, IMAP enabled in gmail, also less secure access turned on
see https://myaccount.google.com/u/3/lesssecureapps
"""

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector

cfg = get_config()["comms"]


def send_email(subject, body, recipients):
    """Sends an email via GMail API"""
    return get_connector().email(subject, body, recipients)


def send_discord_message(content):
    """Sends a message to the techs-live channel"""
    result = get_connector().discord_webhook(cfg["techs_live"], content)
    result.raise_for_status()


def send_help_wanted(content):
    """Sends a message to the help-wanted channel"""
    result = get_connector().discord_webhook(cfg["help_wanted"], content)
    result.raise_for_status()


def send_board_message(content):
    """Sends a message to the board-private channel"""
    result = get_connector().discord_webhook(cfg["board_private"], content)
    result.raise_for_status()


def set_discord_nickname(name, nick):
    """Sets the nickname of a discord user"""
    return get_connector().discord_bot_setnick(name, nick)


def set_discord_role(name, role):
    """Adds a role for a discord user, e.g. Members"""
    return get_connector().discord_bot_setrole(name, role)
