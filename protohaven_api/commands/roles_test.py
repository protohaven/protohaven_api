# pylint: skip-file
"""Tests for role commands"""
from collections import namedtuple

import pytest
import yaml

from protohaven_api.automation.roles import roles as ra
from protohaven_api.automation.roles.roles import DiscordIntent
from protohaven_api.commands import roles as r
from protohaven_api.testing import MatchStr, d, idfn, mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Make CLI fixture"""
    return mkcli(capsys, r)


def test_update_role_intents_various(mocker, cli):
    """Test that various Discord role states are properly handled"""
    data = [
        DiscordIntent(discord_id="a", action="REVOKE", role="Staff"),
        DiscordIntent(discord_id="b", action="ADD", role="Staff"),
    ]
    airtable_data = [
        DiscordIntent(
            discord_id="c",
            action="REVOKE",
            role="Staff",
            state="first_warning",
            last_notified=d(-14),
            rec=123,
        ),
        DiscordIntent(
            discord_id="d",
            action="REVOKE",
            role="Staff",
            state="final_warning",
            last_notified=d(-2),
            rec=456,
        ),
        DiscordIntent(
            discord_id="e",
            action="REVOKE",
            role="Staff",
            state="first_warning",
            last_notified=None,
            rec=999,
        ),
    ]
    mocker.patch.object(r.roles, "gen_role_intents", return_value=data + airtable_data)
    mocker.patch.object(
        r.airtable,
        "get_role_intents",
        return_value=[
            {"id": 1, "fields": {"Discord ID": "notpresent", "Action": "ADD"}},
            {
                "id": 123,
                "fields": {
                    "Discord ID": "c",
                    "Action": "REVOKE",
                    "Role": "Staff",
                    "State": "first_warning",
                    "Last Notified": airtable_data[0].last_notified.isoformat(),
                },
            },
            {
                "id": 456,
                "fields": {
                    "Discord ID": "d",
                    "Action": "REVOKE",
                    "Role": "Staff",
                    "State": "final_warning",
                    "Last Notified": airtable_data[1].last_notified.isoformat(),
                },
            },
            {
                "id": 999,
                "fields": {
                    "Discord ID": "e",
                    "Action": "REVOKE",
                    "Role": "Staff",
                    "State": "first_warning",
                    "Last Notified": None,
                },
            },
        ],
    )
    mocker.patch.object(
        r.airtable, "insert_records", return_value=(200, {"records": [{"id": 789}]})
    )
    mocker.patch.object(r.airtable, "update_record", return_value=(200, None))
    mocker.patch.object(r.airtable, "delete_record", return_value=(200, None))
    mocker.patch.object(ra.comms, "set_discord_role", return_value=True)
    mocker.patch.object(ra.comms, "revoke_discord_role", return_value=True)
    mocker.patch.object(r, "tznow", return_value=d(0))
    got = cli("update_role_intents", ["--apply_records", "--apply_discord"])

    # Revocations A inserted into Airtable since not seen before
    irc = r.airtable.insert_records.mock_calls
    assert {i.args[0][0]["Discord ID"] for i in irc} == {"a"}

    # Addition B carried out with role added
    sdr = ra.comms.set_discord_role.mock_calls
    assert [c[1] for c in sdr] == [("b", "Staff")]

    # C is updated to final warning
    aur = r.airtable.update_record.mock_calls
    assert len(aur) == 1
    assert aur[0].args[3] == airtable_data[0].rec
    assert aur[0].args[0]["State"] == "final_warning"

    # D's revocation is carried out
    rdr = ra.comms.revoke_discord_role.mock_calls
    assert [r[1] for r in rdr] == [("d", "Staff")]

    # D and 'notpresent' removed from airtable
    adr = r.airtable.delete_record.mock_calls
    assert {a.args[2] for a in adr} == {1, 456}

    # E shouldn't be present in other calls, but should be captured in stdout
    got_intents = {i for c in got for i in c.get("intents", [])}
    assert 999 in got_intents


def test_update_role_intents_zero_comms(mocker, cli):
    """Ensure that no comms are sent if there were no changes"""
    mocker.patch.object(r.roles, "gen_role_intents", return_value=[])
    mocker.patch.object(r.airtable, "get_role_intents", return_value=[])

    assert not cli(
        "update_role_intents", ["--apply_records", "--apply_discord", "--destructive"]
    )


def test_enforce_discord_nicknames_zero_comms(mocker, cli):
    """Ensure that no comms are sent if there were no problems"""
    mocker.patch.object(r.comms, "get_all_members", return_value=[])
    mocker.patch.object(
        r.neon, "search_members_with_discord_association", return_value=[]
    )
    mocker.patch.object(r.airtable, "get_notifications_after", return_value={})
    assert not cli("enforce_discord_nicknames", ["--apply", "--warn_not_associated"])


def test_enforce_discord_nicknames(mocker, cli):
    """Ensure that nicknames are enforced and a summary sent; limit not exceeded"""
    mocker.patch.object(
        r.comms,
        "get_all_members",
        return_value=[
            ["usr1", "bad1", d(0)],
            ["usr2", "a b", d(-1)],
            ["usr 3", "not_in_neon", d(-2)],
            ["usr4", "in_neon_non_member", d(-3)],
        ],
    )
    mocker.patch.object(r.airtable, "get_notifications_after", return_value={})
    mocker.patch.object(r.comms, "set_discord_nickname")

    m0 = mocker.MagicMock(discord_user="usr1")
    m0.name = "first last"
    m1 = mocker.MagicMock(discord_user="usr2")
    m1.name = "a b"
    mocker.patch.object(
        r.neon,
        "search_members_with_discord_association",
        return_value=[m0, m1],
    )

    assert cli(
        "enforce_discord_nicknames", ["--apply", "--warn_not_associated", "--limit=1"]
    ) == [
        {
            "body": MatchStr("`bad1` to `first last`"),
            "subject": MatchStr("Nickname changed"),
            "target": "@usr1",
            "id": "usr1_nick_change",
        },
        {
            "body": MatchStr("discord_id=usr%203"),
            "subject": MatchStr("Associate"),
            "target": "@usr 3",
            "id": "not_associated",
        },
        {
            "body": MatchStr("1 nick"),
            "subject": MatchStr("Nickname Automation Summary"),
            "target": "#discord-automation",
        },
    ]
    r.comms.set_discord_nickname.assert_called_once_with("usr1", "first last")


def test_enforce_discord_nicknames_warning_period_observed(mocker, cli):
    """Ensure that warnings about association don't happen too frequently"""
    mocker.patch.object(
        r.comms,
        "get_all_members",
        return_value=[
            ["usr3", "not_in_neon", d(-2)],
        ],
    )
    mocker.patch.object(
        r.airtable, "get_notifications_after", return_value={"@usr3": [d(0)]}
    )
    mocker.patch.object(r.comms, "set_discord_nickname")
    mocker.patch.object(
        r.neon, "search_members_with_discord_association", return_value=[]
    )

    assert (
        cli(
            "enforce_discord_nicknames",
            ["--no-apply", "--warn_not_associated", "--limit=1"],
        )
        == []
    )


def test_setup_discord_user_nickname_change(mocker):
    """Test notification is sent when the nickname is changed"""
    m = mocker.MagicMock(
        neon_id="123", account_current_membership_status="Active", roles=[]
    )
    m.name = "Johnny Doe"
    mocker.patch.object(
        ra.neon,
        "search_members_with_discord_id",
        return_value=[m],
    )
    mocker.patch.object(ra.airtable, "log_comms")

    discord_details = ("discord_user_id", "Old Nickname", None, [])
    actions = list(ra.setup_discord_user(discord_details))

    assert any(
        action == "set_nickname" and args[1] == "Johnny Doe"
        for action, *args in actions
    )
    sent_dm_actions = [args for action, *args in actions if action == "send_dm"]
    assert len(sent_dm_actions) == 2
    assert sent_dm_actions[0] == ["discord_user_id", MatchStr("Johnny Doe")]
