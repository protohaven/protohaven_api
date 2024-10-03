"""Test methods for Discord bot"""
from collections import namedtuple

import pytest

from protohaven_api.discord_bot import PHClient
from protohaven_api.testing import idfn

Tc = namedtuple("tc", "desc,usr,enabled,include,exclude,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("Default", "usr", True, None, None, True),
        Tc("Excluded", "usr", True, None, {"usr"}, False),
        Tc("Not Excluded", "usr", True, None, {"otherusr"}, True),
        Tc("Included", "usr", True, {"usr"}, None, True),
        Tc("Not Included", "usr", True, {"otherusr"}, None, False),
        Tc("Both filters OK", "usr", True, {"usr"}, {"otherusr"}, True),
        Tc(
            "Included but excluded prefers strict", "usr", True, {"usr"}, {"usr"}, False
        ),
        Tc(
            "Not excluded but not included prefers strict",
            "usr",
            True,
            {"usr2"},
            {"usr2"},
            False,
        ),
        Tc("Fail on both filters", "usr", True, {"usr2"}, {"usr"}, False),
    ],
    ids=idfn,
)
def test_hook_on_user_is_permitted(tc, mocker):
    """Test various cases of inclusion/exclusion"""
    mocker.patch.object(
        PHClient,
        "cfg",
        new_callable=mocker.PropertyMock,
        return_value={
            "event_hooks": {
                "enabled": tc.enabled,
                "include_filter": tc.include,
                "exclude_filter": tc.exclude,
            }
        },
    )
    assert (
        PHClient()._hook_on_user_is_permitted(  # pylint: disable=protected-access
            tc.usr
        )
        == tc.want
    )


# async def test_role_edit_add(mocker):
#     """Test adding a role to a user"""
#
# async def test_role_edit_remove(mocker, client):
#     """Test removing a role from a user"""
#     mock_mem = mocker.Mock()
#     mock_mem.remove_roles = mocker.AsyncMock()
#     mocker.patch.object(client.guild, "get_member_named", return_value=mock_mem)
#     client.role_map = {"Members": mocker.MagicMock(id=123)}
#
#     result = await client._role_edit(self, "user1", "Members", "REMOVE")
#     client.guild.get_member_named.assert_called_once_with("user1")
#     mock_mem.remove_roles.assert_awaited_once_with(self.role_map["Members"])
#     assert result is True
#
# async def test_role_edit_user_not_found(mocker):
#     """Test user not found scenario"""
#
# async def test_role_edit_invalid_action(mocker):
#     """Test invalid action scenario"""
#
# async def test_role_edit_http_exception(mocker):
#     """Test HTTPException scenario"""
