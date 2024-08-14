"""Tests for role_automation functions"""
from collections import namedtuple
from dataclasses import replace

import pytest

from protohaven_api.role_automation import roles as r
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
            [("REVOKE", "Members", "membership is inactive")],
        ),
        Tc(
            "Nonactive but matching roles",
            "INACTIVE",
            ["A"],
            ["A"],
            [("REVOKE", "A", "membership is inactive")],
        ),
        Tc(
            "Not associated",
            "NOT_FOUND",
            [],
            ["A"],
            [("REVOKE", "A", "not associated with a Neon account")],
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
    mocker.patch.object(r.neon, "get_active_members", return_value=[])

    # Discord values are fetched from newest to oldest (descending date).
    # Return lots of unique users that incorrectly have the Member role.
    usrs = [
        (f"id{i}", f"nick{i}", d(-i), [("Members", 1234567890)]) for i in range(100)
    ]
    assert usrs[0][0] == "id0"  # Youngest user first
    mocker.patch.object(r.comms, "get_all_members_and_roles", return_value=(usrs, None))
    got = list(r.gen_role_intents(None, None, True, 20))
    assert len(got) == 20  # Cutoff at the passed max
    assert got[0].discord_id == "id99"  # Oldest user is acted upon first


def test_gen_role_intents_match(mocker):
    """Test role intent change when lacking member and instructor roles, but extra shop tech"""

    def mock_fetcher(_):
        return [
            {
                "Account ID": 123,
                "First Name": "A",
                "Last Name": "B",
                "Email 1": "a@b.com",
                "Account Current Membership Status": "ACTIVE",
                "Discord User": "discord_id",
                "API server role": "Instructor",
            }
        ]

    mocker.patch.object(r.neon, "get_active_members", side_effect=mock_fetcher)
    mocker.patch.object(
        r.comms,
        "get_all_members_and_roles",
        return_value=(
            [
                ("discord_id", "nickname", d(0), [("Techs", "techid")]),
            ],
            None,
        ),
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
    mocker.patch.object(r.neon, "get_active_members", return_value=[])
    mocker.patch.object(
        r.comms,
        "get_all_members_and_roles",
        return_value=(
            [
                ("discord_id", "nickname", d(0), [("Techs", "techid")]),
            ],
            None,
        ),
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
