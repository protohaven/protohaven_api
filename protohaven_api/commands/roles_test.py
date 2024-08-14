import pytest
import yaml
from collections import namedtuple
from protohaven_api.rbac import Role
from protohaven_api.commands import roles as r
from protohaven_api.testing import d, idfn

Tc = namedtuple("tc", "desc,neon_member,discord_member,neon_roles,discord_roles,want")
@pytest.mark.parametrize("tc", [
    Tc("Active, no roles", True, False, [], [], [("ADD", "Members")]),
    Tc("Active, missing role", True, False, ["A"], [], [("ADD", "Members"), ("ADD", "A")]),
    Tc("Active, extra role", True, True, [], ["A"], [("REVOKE", "A")]),
    Tc("Active and member, no roles", True, True, [], [], []),
    Tc("Nonactive but member", False, True, [], ["A"], [("REVOKE", "A")]),
    Tc("Nonactive but matching roles", False, False, ["A"], ["A"], [("REVOKE", "A")]),
    ], ids=idfn)
def test_singleton_role_sync(tc):
    assert tc.want == list(r.Commands().singleton_role_sync(tc.neon_member, tc.discord_member, set(tc.neon_roles), set(tc.discord_roles)))

def test_gen_role_intents_limited_and_sorted(mocker):
    """Cuts off role assignment additions if beyond the max"""
    mocker.patch.object(r.neon, 'get_members_with_role', return_value=[])

    # Discord values are fetched from newest to oldest (descending date). Return lots of unique users
    # that incorrectly have the Member role.
    usrs = [
        (f"id{i}", f"nick{i}", d(-i), [("Members", 1234567890)]) for i in range(100)
    ]
    assert usrs[0][0] == "id0" # Youngest user first
    mocker.patch.object(r.comms, 'get_all_members_and_roles', return_value=(usrs, None))
    got = list(r.Commands().gen_role_intents(None, 20))
    assert len(got) == 20 # Cutoff at the passed max
    assert got[0].discord_id == "id99" # Oldest user is acted upon first
    

def test_gen_role_intents_match(mocker):
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
        ("discord_id", "nickname", d(0), [("Techs", "techid")]),
    ], None))
    got = list(r.Commands().gen_role_intents(None, 20))
    want_base = r.DiscordIntent(neon_id=123, name='A B', email='a@b.com', discord_id='discord_id', discord_nick='nickname')
    assert got == [
        want_base._replace(action="ADD", role="Members"),
        want_base._replace(action="REVOKE", role="Techs"),
        want_base._replace(action="ADD", role="Instructors"),
    ]

def test_gen_role_intents_no_neon(mocker):
    """Test intent when discord member has no neon account"""
    mocker.patch.object(r.neon, 'get_members_with_role', return_value=[])
    mocker.patch.object(r.comms, 'get_all_members_and_roles', return_value=([
        ("discord_id", "nickname", d(0), [("Techs", "techid")]),
    ], None))
    got = list(r.Commands().gen_role_intents(None, 20))
    assert got == [
       r.DiscordIntent(discord_id='discord_id', discord_nick='nickname', action="REVOKE", role="Techs"),
    ]

def test_update_role_intents(mocker, capsys):
    data = [
        r.DiscordIntent(discord_id="a", action="REVOKE", role="Staff"), 
        r.DiscordIntent(discord_id="b", action="ADD", role="Staff"), 
    ]
    airtable_data = [
        r.DiscordIntent(discord_id="c", action="REVOKE", role="Staff", state="first_warning", last_notified=d(-14), rec=123), 
        r.DiscordIntent(discord_id="d", action="REVOKE", role="Staff", state="final_warning", last_notified=d(-2), rec=456), 
        r.DiscordIntent(discord_id="e", action="REVOKE", role="Staff", state="first_warning", last_notified=None, rec=999), 
    ]
    mocker.patch.object(r.Commands, "gen_role_intents", return_value=data + airtable_data)
    mocker.patch.object(r.airtable, 'get_role_intents', return_value=[
        {"id": 0, "fields": {"Discord ID": "notpresent", "Action": "ADD"}},
        {"id": 123, "fields": {"Discord ID": "c", "Action": "REVOKE", "Role": "Staff", "State": "first_warning", "Last Notified": airtable_data[0].last_notified.isoformat()}},
        {"id": 456, "fields": {"Discord ID": "d", "Action": "REVOKE", "Role": "Staff", "State": "final_warning", "Last Notified": airtable_data[1].last_notified.isoformat()}},
        {"id": 999, "fields": {"Discord ID": "e", "Action": "REVOKE", "Role": "Staff", "State": "first_warning", "Last Notified": None}},
    ])
    mocker.patch.object(r.airtable, 'insert_records', return_value=(200, {'records': [{'id': 789}]}))
    mocker.patch.object(r.airtable, 'update_record', return_value=(200, None))
    mocker.patch.object(r.airtable, 'delete_record', return_value=(200, None))
    mocker.patch.object(r.comms, 'set_discord_role', return_value=True)
    mocker.patch.object(r.comms, 'revoke_discord_role', return_value=True)
    mocker.patch.object(r, 'tznow', return_value=d(0))
    r.Commands().update_role_intents(["--apply_records", "--apply_discord"])

    # Revocations A inserted into Airtable since not seen before
    irc = r.airtable.insert_records.mock_calls
    assert {i.args[0][0]['Discord ID'] for i in irc} == {'a'}
    
    # Addition B carried out with role added
    sdr = r.comms.set_discord_role.mock_calls
    assert [c[1] for c in sdr] == [('b', 'Staff')]

    # C is updated to final warning
    aur = r.airtable.update_record.mock_calls
    assert len(aur) == 1
    assert aur[0].args[3] == airtable_data[0].rec
    assert aur[0].args[0]['State'] == "final_warning"

    # D's revocation is carried out
    rdr = r.comms.revoke_discord_role.mock_calls
    assert [r[1] for r in rdr] == [('d', 'Staff')]

    # D and 'notpresent' removed from airtable
    adr = r.airtable.delete_record.mock_calls
    assert {a.args[2] for a in adr} == {0, 456}

    # E shouldn't be present in other calls, but should be captured in stdout
    got = yaml.safe_load(capsys.readouterr().out.strip())
    got_intents = {i for c in got for i in c.get('intents', [])}
    assert 999 in got_intents
