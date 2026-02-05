"""Discord, email, and potentially other communications

Required, IMAP enabled in gmail, also less secure access turned on
see https://myaccount.google.com/u/3/lesssecureapps
"""

import logging
import re
import traceback
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, List, Tuple

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from protohaven_api.config import get_config
from protohaven_api.integrations.cronicle import exec_details_footer
from protohaven_api.integrations.data.connector import get as get_connector

log = logging.getLogger("integrations.comms")


@lru_cache(maxsize=1)
def _env():
    loader = PackageLoader("protohaven_api.integrations")
    return (
        Environment(
            loader=loader,
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        ),
        loader,
    )


def get_all_templates() -> List[str]:
    """Returns a list of all templates callable by `render()`"""
    return [e.replace(".jinja2", "") for e in _env()[0].list_templates()]


def render(template_name: str, **kwargs: Any) -> Tuple[str, str, bool]:
    """Returns a rendered template in two parts - subject and body.
    Template must be of the form:

    {% if subject %}Subject goes here!{% else %}Body begins{% endif %}

    HTML template is optionally indicated with {# html #} at the
    very start of the template.
    """
    fname = f"{template_name}.jinja2"
    e, l = _env()
    src, _, _ = l.get_source(e, fname)
    is_html = src.strip().startswith("{# html #}")
    tmpl = e.get_template(fname)
    return (
        tmpl.render(**kwargs, subject=True).strip(),
        tmpl.render(**kwargs, subject=False).strip(),
        is_html,
    )


@dataclass
class Msg:  # pylint: disable=too-many-instance-attributes
    """Msg handles rendering messaging information to a yaml file, for later
    processing with `protohaven_api.cli.send_comms`"""

    target: str
    subject: str
    body: str
    id: str = ""
    intents: list = field(default_factory=list)
    recerts: list = field(default_factory=list)
    side_effect: dict = field(default_factory=dict)
    html: bool = False

    # These field saren't necessary for template rendering, but will be
    # assigned
    EXTRA_FIELDS = ("target", "id", "side_effect", "intents", "recerts")

    @classmethod
    def tmpl(cls, tmpl, **kwargs):
        """Construct a `Msg` object via a template."""
        if "footer" not in kwargs:
            kwargs["footer"] = exec_details_footer()
        subject, body, is_html = render(tmpl, **kwargs)
        self_args = {k: v for k, v in kwargs.items() if k in cls.EXTRA_FIELDS}
        return cls(**self_args, subject=subject, body=body, html=is_html)

    def __iter__(self):
        """Calls of dict(msg) use this function"""
        return iter(
            [
                (k, v)
                for k, v in {
                    "target": self.target,
                    "subject": self.subject,
                    "body": self.body,
                    "id": self.id,
                    "side_effect": self.side_effect,
                    "intents": self.intents,
                    "recerts": self.recerts,
                    "html": self.html,
                }.items()
                if v
            ]
        )


def send_email(subject, body, recipients, html):
    """Sends an email via GMail API"""
    return get_connector().email(subject, body, recipients, html)


# Actual character limit is 2000, but we add some headroom here
DISCORD_CHAR_LIMIT = 1950


def send_discord_message(content, channel=None, blocking=True):
    """Sends a message to the techs-live channel"""
    cfg = get_config("comms")
    if channel is None:
        channel = cfg["webhooks"]["techs-live"]
    elif channel.startswith("@"):  # Send to a user
        return get_connector().discord_bot_fn("send_dm", channel[1:], content)
    elif channel.startswith("#"):  # Send to a channel
        channel = cfg["webhooks"][channel[1:]]
    else:
        raise RuntimeError(f"Unknown channel '{channel}' for discord message")

    # For convenience, any recognizable @role mentions are converted
    # See https://discord.com/developers/docs/reference#message-formatting
    def sub_roles_and_users(m):
        try:
            s = m.group()
            name = m.group()[1:]

            # Skip if it looks like an email domain (e.g., @gmail.com, @yahoo.com)
            # Common email domain pattern: ends with .com, .org, .net, .edu, etc.
            # or contains a dot and looks domain-like
            if "." in name:
                # Check if it ends with a common TLD
                common_tlds = {
                    "com",
                    "org",
                    "net",
                    "edu",
                    "gov",
                    "io",
                    "co",
                    "uk",
                    "us",
                    "ca",
                    "au",
                    "de",
                }
                parts = name.lower().split(".")
                if len(parts) >= 2 and parts[-1] in common_tlds:
                    log.info(f"Skipping email-like mention: @{name}")
                    return s

                # Also skip if it has multiple dots (likely a domain)
                if name.count(".") >= 2:
                    log.info(
                        f"Skipping domain-like mention with multiple dots: @{name}"
                    )
                    return s

            log.info(f"Found potential role/user name in content: @{name}")
            role_id = cfg["discord_roles"].get(name, None)
            if role_id is not None:
                log.info(f"Replacing {s} with role id tag {role_id}")
                return f"<@&{role_id}>"

            user_id = get_connector().discord_bot_fn("resolve_user_id", name)
            if user_id is not None:
                log.info(f"Replacing {s} with user id tag {user_id}")
                return f"<@{user_id}>"
            log.info("No user or role match; leaving it alone")
            return s
        except Exception:  # pylint: disable=broad-exception-caught
            traceback.print_exc()  # We shouldn't let substitution failing prevent message sending
            log.info(
                "Ignoring discord role/user resolution failure; continuing anyways..."
            )
            return s

    # Usernames are alphanumeric and can contain periods and underscores
    # https://gamertweak.com/new-username-system-discord/
    # Improved regex: @ followed by 2+ chars of [a-zA-Z0-9._], not matching if @ is preceded by word char
    # This avoids matching email addresses like user@gmail.com
    content = re.sub(
        r"(?<!\w)@[\w\._]{2,}", sub_roles_and_users, content, flags=re.MULTILINE
    )

    for i in range(0, len(content), DISCORD_CHAR_LIMIT):
        chunk = content[i : i + DISCORD_CHAR_LIMIT]
        log.info(f"Sending msg ({len(chunk)}/{len(content)} chars)")
        result = get_connector().discord_webhook(channel, chunk)
        if blocking:
            result.raise_for_status()
    return result


def set_discord_nickname(name, nick):
    """Sets the nickname of a discord user"""
    return get_connector().discord_bot_fn("set_nickname", name, nick)


def set_discord_role(name, role):
    """Adds a role for a discord user, e.g. Members"""
    return get_connector().discord_bot_fn("grant_role", name, role)


def revoke_discord_role(name, role):
    """Removes a role for a discord user"""
    return get_connector().discord_bot_fn("revoke_role", name, role)


def get_all_members():
    """Gets all members and roles on Discord"""
    return get_connector().discord_bot_fn("get_all_members")


def get_member_details(discord_id):
    """Gets specific discord's member details"""
    return get_connector().discord_bot_fn("get_member_details", discord_id)


def get_member_channels():
    """Fetches a list of channels that members can view"""
    return get_connector().discord_bot_fn("get_member_channels")


def get_channel_history(channel_id, from_date, to_date, max_length=10000):
    """Get a list of messages from a channel between two dates"""
    yield from get_connector().discord_bot_genfn(
        "get_channel_history", channel_id, from_date, to_date, max_length
    )
