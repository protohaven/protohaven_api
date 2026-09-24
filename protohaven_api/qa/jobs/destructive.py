"""QA tests for destructive Cronicle jobs."""

# pylint: disable=missing-function-docstring

from protohaven_api.integrations import neon
from protohaven_api.qa.base import (
    QAContext,
    assert_log_contains,
    assert_no_comms_sent,
    assert_sent_discord,
)
from protohaven_api.qa.fixtures import discord as discord_fixture
from protohaven_api.qa.fixtures import neon as neon_fixture


def test_discord_nick(ctx: QAContext):
    acct = neon_fixture.create_mock_account(ctx, "discord-nick")
    neon.set_discord_user(acct.neon_id, discord_fixture.DISCORD_USER)
    discord_fixture.set_nickname(ctx, "QA Old Nickname")

    result = ctx.run(
        "enforce_discord_nicknames",
        "elzx3nvdvu4",
        f"--apply --filter={discord_fixture.DISCORD_USER} --limit=1 --no-warn_not_associated",
        send_comms=True,
        dm=True,
    )
    assert result.code == 0
    assert_sent_discord(result)
    assert_log_contains(result.text, ["discord_nick_changed"])


def test_discord_role(ctx: QAContext):
    result = ctx.run(
        "update_role_intents",
        "elzsp1fmpsk",
        (
            f"--filter={discord_fixture.DISCORD_USER} "
            "--apply_records --no-apply_discord --no-destructive "
            "--max_users_added=0 --max_users_removed=0"
        ),
        send_comms=True,
    )
    assert result.code == 0
    assert_no_comms_sent(result)


def test_init_memberships(ctx: QAContext):
    result = ctx.run(
        "init_new_memberships",
        "em1zpg3sc9r",
        "--no-apply --limit=0",
        send_comms=True,
    )
    assert result.code == 0
    assert_no_comms_sent(result)


def test_cleanup_orphaned_class_reservations(ctx: QAContext):
    result = ctx.run(
        "cleanup_orphaned_class_reservations",
        "emmtkylp1m7",
        "--no-apply --max=1 --days=7",
        send_comms=True,
    )
    assert result.code == 0
    assert_no_comms_sent(result)
