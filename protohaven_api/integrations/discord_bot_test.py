"""Test methods for Discord bot"""

from collections import namedtuple

import pytest
from discord import DMChannel, HTTPException

from protohaven_api.integrations import discord_bot as db
from protohaven_api.testing import d, idfn

Tc = namedtuple("Tc", "desc,usr,enabled,include,exclude,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("Disabled", "usr", False, "usr, usr2", "None", False),
        Tc("Default", "usr", True, "None", "None", True),
        Tc("Excluded", "usr", True, "None", "usr", False),
        Tc("Not Excluded", "usr", True, "None", "otherusr", True),
        Tc("Included", "usr", True, "usr", "None", True),
        Tc("Not Included", "usr", True, "otherusr", "None", False),
        Tc("Both filters OK", "usr", True, "usr", "otherusr", True),
        Tc("Included but excluded prefers strict", "usr", True, "usr", "usr", False),
        Tc(
            "Not excluded but not included prefers strict",
            "usr",
            True,
            "usr2",
            "usr2",
            False,
        ),
        Tc("Fail on both filters", "usr", True, "usr2", "usr", False),
    ],
    ids=idfn,
)
def test_hook_on_user_is_permitted(tc, mocker):
    """Test various cases of inclusion/exclusion"""
    mocker.patch.object(
        db,
        "get_config",
        side_effect=lambda p, as_bool=None: {
            "enabled": tc.enabled,
            "include_filter": tc.include,
            "exclude_filter": tc.exclude,
        }.get(p.split("/")[-1]),
    )
    assert db.PHClient(intents=None).hook_on_user_is_permitted(tc.usr) == tc.want


@pytest.fixture(name="discord_bot")
def fixture_discord_bot(mocker):
    """Provide discord bot as fixture"""
    bot = db.PHClient(intents=None)
    bot.get_guild = mocker.MagicMock()
    bot.role_map = {"Members": mocker.Mock()}
    return bot


def _message(mocker, content="TEST_MEMBER_JOIN"):
    """Build a DM message mock for on_message tests"""
    author = mocker.MagicMock()
    author.name = "Test Member"
    author.id = 999
    msg = mocker.MagicMock()
    msg.author = author
    msg.channel = mocker.MagicMock(spec=DMChannel)
    msg.content = content
    return msg


@pytest.mark.asyncio
async def test_on_message_test_member_join_runs_hook(discord_bot, mocker):
    """TEST_MEMBER_JOIN DM dispatches each member_join_hook_fn action"""
    msg = _message(mocker)
    member = mocker.MagicMock()
    discord_bot.guild.get_member.return_value = member
    mocker.patch.object(discord_bot, "hook_on_user_is_permitted", return_value=True)
    mocker.patch.object(discord_bot, "handle_hook_action", new=mocker.AsyncMock())
    mocker.patch.object(db, "client", mocker.MagicMock())
    details = ("999", "Test Member", d(0), [])
    mocker.patch.object(discord_bot, "_member_details", return_value=details)
    discord_bot.member_join_hook_fn = mocker.Mock(
        return_value=[("send_dm", "999", "associate")]
    )

    await discord_bot.on_message(msg)

    discord_bot.member_join_hook_fn.assert_called_once_with(details)
    discord_bot.handle_hook_action.assert_awaited_once_with(
        "send_dm", "999", "associate"
    )


@pytest.mark.asyncio
async def test_on_message_test_member_join_ignored_when_not_permitted(
    discord_bot, mocker
):
    """TEST_MEMBER_JOIN does not run the hook for non-permitted authors"""
    msg = _message(mocker)
    mocker.patch.object(discord_bot, "hook_on_user_is_permitted", return_value=False)
    discord_bot.member_join_hook_fn = mocker.Mock()

    await discord_bot.on_message(msg)

    discord_bot.member_join_hook_fn.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_test_member_join_ignored_when_not_in_guild(
    discord_bot, mocker
):
    """TEST_MEMBER_JOIN from a DM user outside the guild is ignored"""
    msg = _message(mocker)
    discord_bot.guild.get_member.return_value = None
    mocker.patch.object(discord_bot, "hook_on_user_is_permitted", return_value=True)
    mocker.patch.object(db, "client", mocker.MagicMock())
    discord_bot.member_join_hook_fn = mocker.Mock()

    await discord_bot.on_message(msg)

    discord_bot.member_join_hook_fn.assert_not_called()


@pytest.mark.asyncio
async def test_grant_role_success(discord_bot, mocker):
    """Test granting a role"""
    member = mocker.AsyncMock()
    discord_bot.guild.get_member_named.return_value = member
    result = await discord_bot.grant_role("test_user", "Members")
    member.add_roles.assert_awaited_once_with(discord_bot.role_map["Members"])
    assert result is True


@pytest.mark.asyncio
async def test_grant_role_user_not_found(discord_bot):
    """Test when user not found to grant"""
    discord_bot.guild.get_member_named.return_value = None
    result = await discord_bot.grant_role("unknown_user", "Members")
    assert result is False


@pytest.mark.asyncio
async def test_grant_role_http_exception(discord_bot, mocker):
    """Test when granting fails"""
    member = mocker.AsyncMock()
    discord_bot.guild.get_member_named.return_value = member
    member.add_roles.side_effect = HTTPException(mocker.MagicMock(), "HTTP error")
    result = await discord_bot.grant_role("test_user", "Members")
    assert "HTTP error" in result


@pytest.mark.asyncio
async def test_revoke_role_success(discord_bot, mocker):
    """Test success case when revoking role"""
    member = mocker.AsyncMock()
    discord_bot.guild.get_member_named.return_value = member
    result = await discord_bot.revoke_role("test_user", "Members")
    member.remove_roles.assert_awaited_once_with(discord_bot.role_map["Members"])
    assert result is True


@pytest.mark.asyncio
async def test_revoke_role_user_not_found(discord_bot):
    """Test when user not found to revoke"""
    discord_bot.guild.get_member_named.return_value = None
    result = await discord_bot.revoke_role("unknown_user", "Members")
    assert result is False


@pytest.mark.asyncio
async def test_revoke_role_http_exception(discord_bot, mocker):
    """Test when revocation fails"""
    member = mocker.AsyncMock()
    discord_bot.guild.get_member_named.return_value = member
    member.remove_roles.side_effect = HTTPException(mocker.MagicMock(), "HTTP error")
    result = await discord_bot.revoke_role("test_user", "Members")
    assert "HTTP error" in result
