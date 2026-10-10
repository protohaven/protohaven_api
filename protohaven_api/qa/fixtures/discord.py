"""Discord QA fixture helpers for the dedicated QA user.

The QA runner does not start the Discord bot (Cronicle child jobs start their
own short-lived bot instances). These helpers use the Discord REST API
directly so setup and cleanup can be performed from the runner without a
local bot client.
"""

import requests

from protohaven_api.config import get_config
from protohaven_api.qa.base import QA_DM, QAContext

DISCORD_USER = QA_DM.removeprefix("@")
DISCORD_API = "https://discord.com/api/v10"


def _headers() -> dict:
    return {"Authorization": f"Bot {get_config('discord_bot/token')}"}


def _guild_id() -> int:
    return int(get_config("discord_bot/guild_id"))


def _request(method: str, path: str, **kwargs):
    rep = requests.request(
        method,
        f"{DISCORD_API}{path}",
        headers=_headers(),
        timeout=30,
        **kwargs,
    )
    rep.raise_for_status()
    if rep.content:
        return rep.json()
    return None


def _roles() -> dict[str, str]:
    return {r["name"]: r["id"] for r in _request("GET", f"/guilds/{_guild_id()}/roles")}


def _find_member() -> dict:
    members = _request("GET", f"/guilds/{_guild_id()}/members?limit=1000")
    for member in members:
        user = member.get("user") or {}
        if user.get("username") == DISCORD_USER or member.get("nick") == DISCORD_USER:
            return member
    raise RuntimeError(f"QA Discord user not found: {DISCORD_USER}")


def _member_id(member: dict) -> str:
    return member["user"]["id"]


def _member() -> tuple:
    """Return (username, display_name, joined_at, roles) for the QA user."""
    member = _find_member()
    user = member.get("user") or {}
    role_map = _roles()
    roles = [
        (
            next((name for name, role_id in role_map.items() if role_id == rid), rid),
            rid,
        )
        for rid in member.get("roles", [])
    ]
    return (
        user.get("username"),
        member.get("nick") or user.get("username"),
        member.get("joined_at"),
        roles,
    )


def set_nickname(ctx: QAContext, nick: str) -> None:
    """Set a nickname on the QA Discord user and restore the original later."""
    member = _find_member()
    original = _member()[1]
    _request(
        "PATCH",
        f"/guilds/{_guild_id()}/members/{_member_id(member)}",
        json={"nick": nick},
    )
    ctx.cleanup.register(
        f"restore Discord nickname for {DISCORD_USER}",
        lambda: _request(
            "PATCH",
            f"/guilds/{_guild_id()}/members/{_member_id(member)}",
            json={"nick": original},
        ),
    )


def has_role(role: str) -> bool:
    """Return True if the QA Discord user currently has the named role."""
    role_id = _roles().get(role)
    if role_id is None:
        raise RuntimeError(f"Discord role not found: {role}")
    return role_id in _find_member().get("roles", [])


def set_role(role: str) -> None:
    """Grant a role to the QA Discord user."""
    member = _find_member()
    role_id = _roles().get(role)
    if role_id is None:
        raise RuntimeError(f"Discord role not found: {role}")
    _request(
        "PUT",
        f"/guilds/{_guild_id()}/members/{_member_id(member)}/roles/{role_id}",
    )


def remove_role(role: str) -> None:
    """Revoke a role from the QA Discord user."""
    member = _find_member()
    role_id = _roles().get(role)
    if role_id is None:
        raise RuntimeError(f"Discord role not found: {role}")
    _request(
        "DELETE",
        f"/guilds/{_guild_id()}/members/{_member_id(member)}/roles/{role_id}",
    )


def grant_role(ctx: QAContext, role: str) -> None:
    """Grant a role to the QA Discord user and revoke it later."""
    set_role(role)
    ctx.cleanup.register(
        f"revoke Discord role {role} from {DISCORD_USER}", lambda: remove_role(role)
    )


def revoke_role(ctx: QAContext, role: str) -> None:
    """Revoke a role from the QA Discord user and restore it later."""
    remove_role(role)
    ctx.cleanup.register(
        f"restore Discord role {role} for {DISCORD_USER}", lambda: set_role(role)
    )
