# pylint: skip-file
"""Tests for role_automation functions"""
from collections import namedtuple
from dataclasses import replace

import pytest

from protohaven_api.automation.roles import roles as r
from protohaven_api.testing import d, idfn

Tc = namedtuple("tc", "desc,neon_member,neon_roles,discord_roles,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc(
            "Active, no roles",
            "ACTIVE",
            [],
            [],
            [("ADD", "Members", "indicated by Neon CRM")],
        ),
        Tc(
            "Future, no roles",
            "FUTURE",
            [],
            [],
            [("ADD", "Members", "indicated by Neon CRM")],
        ),
        Tc(
            "Active, missing role",
            "ACTIVE",
            ["A"],
            ["Members"],
            [("ADD", "A", "indicated by Neon CRM")],
        ),
        Tc(
            "Active, extra role",
            "ACTIVE",
            [],
            ["Members", "A"],
            [("REVOKE", "A", "not indicated by Neon CRM")],
        ),
        Tc("Active and member, no roles", "ACTIVE", [], ["Members"], []),
        Tc("Active and member, all roles OK", "ACTIVE", ["A"], ["Members", "A"], []),
        Tc(
            "Nonactive but member",
            "INACTIVE",
            [],
            ["Members"],
            # [("REVOKE", "Members", "membership is inactive")],
            [],  # We don't revoke member roles currently
        ),
        Tc(
            "Nonactive but matching roles",
            "INACTIVE",
            ["A"],
            ["A"],
            # [("REVOKE", "A", "membership is inactive")],
            [],  # We don't revoke inactive membership roles currently
        ),
        Tc(
            "Not associated",
            "NOT_FOUND",
            [],
            ["A"],
            [("REVOKE", "A", "not associated with a Neon account")],
        ),
        Tc(
            "@everyone role is ignored",
            "INACTIVE",
            [],
            ["@everyone"],
            [],
        ),
    ],
    ids=idfn,
)
def test_singleton_role_sync(tc):
    """Tests various outcomes based on neon membership, roles, and discord roles"""
    assert tc.want == list(
        r.singleton_role_sync(tc.neon_member, set(tc.neon_roles), set(tc.discord_roles))
    )


def test_gen_role_intents_limited_and_sorted(mocker):
    """Cuts off role assignment additions if beyond the max"""
    mocker.patch.object(
        r.neon, "search_members_with_discord_association", return_value=[]
    )

    # Discord values are fetched from newest to oldest (descending date).
    # Return lots of unique users that incorrectly have the Shop Tech role.
    usrs = [(f"id{i}", f"nick{i}", d(-i), [("Techs", 1234567890)]) for i in range(100)]
    assert usrs[0][0] == "id0"  # Youngest user first
    mocker.patch.object(r.comms, "get_all_members", return_value=usrs)
    got = list(r.gen_role_intents(None, None, True, 20))
    assert len(got) == 20  # Cutoff at the passed max
    assert got[0].discord_id == "id99"  # Oldest user is acted upon first


def test_gen_role_intents_departing_member(mocker):
    """Test role intent change when prior member is no longer active"""

    def mock_fetcher(_):
        return [
            mocker.MagicMock(
                neon_id=123,
                fname="A",
                lname="B",
                email="a@b.com",
                account_current_membership_statu="Inactive",
                discord_user="discord_id",
                roles=[],
            )
        ]

    mocker.patch.object(
        r.neon, "search_members_with_discord_association", side_effect=mock_fetcher
    )
    mocker.patch.object(
        r.comms,
        "get_all_members",
        return_value=[
            ("discord_id", "nickname", d(0), [("Members", "memid")]),
        ],
    )
    assert list(r.gen_role_intents(None, None, True, 20)) == []


def test_gen_role_intents_match(mocker):
    """Test role intent change when lacking member and instructor roles, but extra shop tech"""

    def mock_fetcher(_):
        return [
            mocker.MagicMock(
                neon_id=123,
                fname="A",
                lname="B",
                name="A B",
                email="a@b.com",
                account_current_membership_status="Active",
                discord_user="discord_id",
                roles=[{"name": "Instructor"}],
            )
        ]

    mocker.patch.object(
        r.neon, "search_members_with_discord_association", side_effect=mock_fetcher
    )
    mocker.patch.object(
        r.comms,
        "get_all_members",
        return_value=[
            ("discord_id", "nickname", d(0), [("Techs", "techid")]),
        ],
    )
    got = list(r.gen_role_intents(None, None, True, 20))
    want_base = r.DiscordIntent(
        neon_id=123,
        name="A B",
        email="a@b.com",
        discord_id="discord_id",
        discord_nick="nickname",
    )
    want = [
        replace(
            want_base, action="REVOKE", role="Techs", reason="not indicated by Neon CRM"
        ),
        replace(
            want_base, action="ADD", role="Instructors", reason="indicated by Neon CRM"
        ),
        replace(
            want_base, action="ADD", role="Members", reason="indicated by Neon CRM"
        ),
    ]

    got.sort(key=lambda g: g.role)
    want.sort(key=lambda w: w.role)
    assert got == want


def test_gen_role_intents_no_neon(mocker):
    """Test intent when discord member has no neon account"""
    mocker.patch.object(
        r.neon, "search_members_with_discord_association", return_value=[]
    )
    mocker.patch.object(
        r.comms,
        "get_all_members",
        return_value=[
            ("discord_id", "nickname", d(0), [("Techs", "techid")]),
        ],
    )
    got = list(r.gen_role_intents(None, None, True, 20))
    assert got == [
        r.DiscordIntent(
            discord_id="discord_id",
            discord_nick="nickname",
            action="REVOKE",
            role="Techs",
            reason="not associated with a Neon account",
        ),
    ]


def test_sync_delayed_intents_toggling_apply(mocker):
    """Setting apply_records to False prevents comms and does not
    call airtable; setting to True does"""
    mocker.patch.object(r.airtable, "delete_record", return_value=(200, None))
    mocker.patch.object(
        r.airtable, "insert_records", return_value=(200, {"records": [{"id": "456"}]})
    )

    i1 = r.DiscordIntent(
        discord_id="foo",
        rec="123",
        action="REVOKE",
    )
    i2 = r.DiscordIntent(
        discord_id="foo",
        action="REVOKE",
    )
    got = {"foo": []}

    # Behavior without applying records
    r.sync_delayed_intents(
        intents={i2.rec: i2},
        airtable_intents={i1.rec: i1},
        user_log=got,
        apply_records=False,
    )
    r.airtable.insert_records.assert_not_called()
    r.airtable.delete_record.assert_not_called()
    assert not got["foo"]

    # Behavior with applying records
    r.sync_delayed_intents(
        intents={i2.rec: i2},
        airtable_intents={i1.rec: i1},
        user_log=got,
        apply_records=True,
    )
    r.airtable.insert_records.assert_called()
    r.airtable.delete_record.assert_called()
    got["foo"].sort(key=lambda i: i[0])
    assert got["foo"] == [
        ("CANCELED: revoke Discord role None (Now present in Neon CRM)", "123"),
        ("IN 14 DAYS: revoke Discord role None (None)", "456"),
    ]


def test_setup_discord_user_not_associated(mocker):
    """If user isn't associated with neon, return association request"""
    mocker.patch.object(r.neon, "search_members_with_discord_id", return_value=[])
    mocker.patch.object(r.airtable, "log_comms")
    got = list(r.setup_discord_user(("a", "a", None, [])))
    assert len(got) == 1
    assert got[0][0] == "send_dm"
    assert got[0][1] == "a"
    content = got[0][2]
    assert "**Action Requested - Associate Your Discord User:**" in content
    assert "https://api.protohaven.org/member?discord_id=a" in content
    r.airtable.log_comms.assert_called()


def test_setup_discord_nonmember_nodiffs(mocker):
    """Non-member with zero diffs gets zero response"""
    m = mocker.MagicMock(
        neon_id=1,
        account_current_membership_status="Inactive",
    )

    m.name = "a"  # Name is a special attr
    mocker.patch.object(
        r.neon,
        "search_members_with_discord_id",
        return_value=[m],
    )
    got = list(r.setup_discord_user(("a", "a", None, [])))
    assert not got


def test_setup_discord_user_no_diffs(mocker):
    """If the user is set up properly and there's no action to take, no
    message is returned."""
    m = mocker.MagicMock(
        neon_id=1,
        account_current_membership_status="Active",
        roles=[{"name": "Instructor"}, {"name": "Shop Tech"}],
    )

    m.name = "a"  # Name is a special attr
    mocker.patch.object(
        r.neon,
        "search_members_with_discord_id",
        return_value=[m],
    )
    got = list(
        r.setup_discord_user(
            ("a", "a", None, [("Instructors", 123), ("Techs", 456), ("Members", 789)])
        )
    )
    assert not got


def test_setup_discord_user_nickname_change(mocker):
    """Nickname change is passed to discord bot"""
    m = mocker.MagicMock(
        neon_id=1,
        account_current_membership_status="Active",
    )

    m.name = "b"  # Name is a special attr
    mocker.patch.object(
        r.neon,
        "search_members_with_discord_id",
        return_value=[m],
    )
    got = list(r.setup_discord_user(("a", "a", None, [("Members", 123)])))
    assert len(got) == 2
    assert got[0] == ("set_nickname", "a", "b")


def test_setup_discord_user_multiple_accounts(mocker):
    """Multiple accounts with active user is handled OK"""
    m0 = mocker.MagicMock(
        neon_id=1,
        account_current_membership_status="Inactive",
        roles=[{"name": "Instructor"}],
    )

    m0.name = "a"  # Name is a special attr
    m1 = mocker.MagicMock(
        neon_id=1,
        account_current_membership_status="Active",
        roles=[],
    )

    m1.name = "a"  # Name is a special attr

    mocker.patch.object(
        r.neon,
        "search_members_with_discord_id",
        return_value=[m0, m1],
    )
    got = list(r.setup_discord_user(("a", "a", None, [])))
    assert len(got) == 3
    assert ("grant_role", "a", "Instructors") in got
    assert ("grant_role", "a", "Members") in got
