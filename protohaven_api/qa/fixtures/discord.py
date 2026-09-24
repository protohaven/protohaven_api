"""Discord QA fixture helpers for the dedicated QA user."""

from protohaven_api.integrations import comms
from protohaven_api.qa.base import QA_DM, QAContext

DISCORD_USER = QA_DM.removeprefix("@")


def _member() -> tuple:
    for member in comms.get_all_members():
        if member[0] == DISCORD_USER:
            return member
    raise RuntimeError(f"QA Discord user not found: {DISCORD_USER}")


def set_nickname(ctx: QAContext, nick: str) -> None:
    """Set a nickname on the QA Discord user and restore the original later."""
    original = _member()[1]
    comms.set_discord_nickname(DISCORD_USER, nick)
    ctx.cleanup.register(
        f"restore Discord nickname for {DISCORD_USER}",
        lambda: comms.set_discord_nickname(DISCORD_USER, original),
    )


def grant_role(ctx: QAContext, role: str) -> None:
    """Grant a role to the QA Discord user and revoke it later."""
    comms.set_discord_role(DISCORD_USER, role)
    ctx.cleanup.register(
        f"revoke Discord role {role} from {DISCORD_USER}",
        lambda: comms.revoke_discord_role(DISCORD_USER, role),
    )


def revoke_role(ctx: QAContext, role: str) -> None:
    """Revoke a role from the QA Discord user and restore it later."""
    comms.revoke_discord_role(DISCORD_USER, role)
    ctx.cleanup.register(
        f"restore Discord role {role} for {DISCORD_USER}",
        lambda: comms.set_discord_role(DISCORD_USER, role),
    )
