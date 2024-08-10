import pytest
from collections import namedtuple
from protohaven_api.rbac import Role
from protohaven_api.commands import roles as r
from protohaven_api.testing import idfn

Tc = namedtuple("tc", "desc,neon_member,discord_member,neon_roles,discord_roles,want")
@pytest.mark.parametrize("tc", [
    Tc("Active, no roles", True, False, [], [], [(r.Action.ADD_MEMBER, None)]),
    Tc("Active, missing role", True, False, ["A"], [], [(r.Action.ADD_MEMBER, None), (r.Action.ADD, "A")]),
    Tc("Active, extra role", True, True, [], ["A"], [(r.Action.REVOKE, "A")]),
    Tc("Active and member, no roles", True, True, [], [], []),
    Tc("Nonactive but member", False, True, [], [], [(r.Action.REVOKE_ALL, None)]),
    Tc("Nonactive but matching roles", False, False, ["A"], ["A"], [(r.Action.REVOKE_ALL, None)]),
    ], ids=idfn)
def test_singleton_role_sync(tc):
    assert tc.want == list(r.Commands().singleton_role_sync(tc.neon_member, tc.discord_member, set(tc.neon_roles), set(tc.discord_roles)))


def test_compute_role_assignment_intent_safety(mocker):
    """Raises exception if neon data returned is unexpectedly small"""
    # TODO

def test_compute_role_assignment_intent_match(mocker):
    """Test role intent change when lacking member and instructor roles, but extra shop tech"""
    def mock_fetcher(r, _):
        return [{
                'Account ID': 123,
                'First Name': 'A',
                'Last Name': 'B',
                'Email 1': 'a@b.com',
                'Account Current Membership Status': 'ACTIVE',
                'Discord User': 'discord_id',
            }] if r == Role.INSTRUCTOR else []

    mocker.patch.object(r.neon, 'get_members_with_role', side_effect=mock_fetcher)
    mocker.patch.object(r.comms, 'get_all_members_and_roles', return_value=([
        ("discord_id", "nickname", [("Techs", "techid")]),
    ], None))
    got = list(r.Commands().compute_role_assignment_intent())
    want_base = r.DiscordIntent(neon_id=123, name='A B', email='a@b.com', discord_id='discord_id', discord_nick='nickname')
    assert got == [
        want_base._replace(action=r.Action.ADD_MEMBER),
        want_base._replace(action=r.Action.REVOKE, role="Shop Tech"),
        want_base._replace(action=r.Action.ADD, role="Instructor"),
    ]

def test_compute_role_assignment_no_neon(mocker):
    """Test intent when discord member has no neon account"""
    mocker.patch.object(r.neon, 'get_members_with_role', return_value=[])
    mocker.patch.object(r.comms, 'get_all_members_and_roles', return_value=([
        ("discord_id", "nickname", [("Techs", "techid")]),
    ], None))
    got = list(r.Commands().compute_role_assignment_intent())
    assert got == [
       r.DiscordIntent(discord_id='discord_id', discord_nick='nickname', action=r.Action.REVOKE_ALL),
    ]
