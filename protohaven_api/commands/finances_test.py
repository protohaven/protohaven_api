"""Test methods for finance-oriented CLI commands"""

# pylint: skip-file
import datetime

import pytest
import yaml
from dateutil import parser as dateparser

from protohaven_api.commands import finances as f
from protohaven_api.config import tznow  # pylint: disable=import-error
from protohaven_api.integrations import neon  # pylint: disable=import-error
from protohaven_api.testing import MatchStr, d, mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    return mkcli(capsys, f)


def test_transaction_alerts_ok(mocker, cli):
    mocker.patch.object(
        f.sales, "get_customer_name_map", return_value={"cust_id": "Foo Bar"}
    )
    mocker.patch.object(
        f.sales,
        "get_subscription_plan_map",
        return_value={
            "var_id": ("plan_id", 50),
        },
    )
    mocker.patch.object(f, "tznow", return_value=d(0))
    mocker.patch.object(
        f.sales,
        "get_subscriptions",
        return_value={
            "subscriptions": [
                {
                    "status": "ACTIVE",
                    "id": "sub_id",
                    "plan_variation_id": "var_id",
                    "customer_id": "cust_id",
                    "charged_through_date": d(0).isoformat(),
                }
            ]
        },
    )
    mocker.patch.object(f.sales, "subscription_tax_pct", return_value=7.0)
    got = cli("transaction_alerts", [])
    assert not got


def test_validate_memberships_empty(mocker):
    """Empty search shoud pass by default"""
    mocker.patch.object(neon, "search_member", return_value=[])
    got = list(f.Commands()._validate_memberships_internal())
    assert not got


def test_validate_membership_amp_ok():
    """Amp member should pass validation if they are marked appropriately for their term"""
    got = f.Commands()._validate_membership_singleton(
        {
            "level": "AMP",
            "term": "Extremely Low Income",
            "amp": {"optionValues": ["ELI"]},
            "active_memberships": [{"fee": 1, "end_date": d(5)}],
        },
        d(0),
    )
    assert not got


def test_validate_multi_membership_bad():
    """All memberships should have an end date"""
    got = f.Commands()._validate_membership_singleton(
        {
            "level": "General Membership",
            "active_memberships": [
                {"fee": 1, "end_date": d(5), "level": "General Membership"},
                {"fee": 1, "end_date": d(5), "level": "General Membership"},
            ],
        },
        d(0),
    )
    assert got == ["Multiple active memberships: 2 total"]


def test_validate_multi_membership_future_start_date_ok():
    """All memberships should have an end date"""
    got = f.Commands()._validate_membership_singleton(
        {
            "level": "General Membership",
            "active_memberships": [
                {"fee": 1, "end_date": d(5), "level": "General Membership"},
                {
                    "fee": 1,
                    "start_date": d(1),
                    "end_date": d(10),
                    "level": "General Membership",
                },
            ],
        },
        d(0),
    )
    assert not got


def test_validate_multi_membership_refunded_ok():
    """All memberships should have an end date"""
    got = f.Commands()._validate_membership_singleton(
        {
            "level": "General Membership",
            "active_memberships": [
                {"fee": 1, "end_date": d(5), "level": "General Membership"},
                {
                    "fee": 1,
                    "end_date": d(5),
                    "level": "General Membership",
                    "status": "REFUNDED",
                },
            ],
        },
        d(0),
    )
    assert not got


def test_validate_membership_no_end_date_bad():
    """All memberships should have an end date"""
    got = f.Commands()._validate_membership_singleton(
        {
            "level": "General Membership",
            "active_memberships": [{"fee": 1, "level": "General Membership"}],
        }
    )
    assert got == ["Membership General Membership with no end date (infinite duration)"]


def test_validate_membership_zero_cost_roles_ok():
    """Various roles that are $0 memberships should validate OK"""
    for l, r in [
        ("Shop Tech", "Shop Tech"),
        ("Board Member", "Board Member"),
        ("Staff", "Staff"),
        ("Software Developer", "Software Dev"),
    ]:
        got = f.Commands()._validate_membership_singleton(
            {
                "level": l,
                "roles": [r],
                "active_memberships": [{"fee": 0, "level": l, "end_date": d(1)}],
            },
            d(0),
        )
    assert not got


def test_validate_membership_general_zero_cost_bad():
    """General membership should always cost money, unless explicitly marked"""
    got = f.Commands()._validate_membership_singleton(
        {
            "level": "General Membership",
            "active_memberships": [
                {"fee": 0, "level": "General Membership", "end_date": d(1)}
            ],
            "zero_cost_ok_until": tznow() - datetime.timedelta(days=1),
        },
        d(0),
    )
    assert got == [MatchStr("Abnormal zero-cost membership General Membership")]

    got = f.Commands()._validate_membership_singleton(
        {
            "level": "General Membership",
            "active_memberships": [
                {"fee": 0, "level": "General Membership", "end_date": d(1)}
            ],
            "zero_cost_ok_until": tznow() + datetime.timedelta(days=1),
        },
        d(0),
    )
    assert not got


def test_validate_membership_instructor_ok():
    """Instructor should validate when role is applied"""
    got = f.Commands()._validate_membership_singleton(
        {
            "level": "Instructor",
            "roles": ["Instructor"],
            "active_memberships": [{"fee": 1, "end_date": d(1)}],
        },
        d(0),
    )
    assert not got


def test_validate_membership_instructor_no_role():
    """Raise validation error for instructor without role"""
    got = f.Commands()._validate_membership_singleton(
        {
            "level": "Instructor",
            "roles": [],
            "active_memberships": [{"fee": 1, "end_date": d(1)}],
        },
        d(0),
    )
    assert got == ["Needs role Instructor, has []"]


def test_validate_membership_addl_family_ok():
    """Conforming additional family member"""
    got = f.Commands()._validate_membership_singleton(
        {
            "hid": "123",
            "household_paying_member_count": 1,
            "household_num_addl_members": 1,
            "level": "Additional Family Membership",
            "active_memberships": [{"fee": 1, "end_date": d(1)}],
        },
        d(0),
    )
    assert not got


def test_validate_membership_addl_family_no_fullprice_bad():
    """Addl membership without a paid membership in the household is a no-no"""
    got = f.Commands()._validate_membership_singleton(
        {
            "hid": "123",
            "household_paying_member_count": 0,
            "household_num_addl_members": 2,
            "level": "Additional Family Membership",
            "active_memberships": [{"fee": 1, "end_date": d(1)}],
        },
        d(0),
    )
    assert got == ["Missing required non-additional paid member in household #123"]


def test_validate_membership_employer_ok():
    """Corporate memberships with two members are OK"""
    got = f.Commands()._validate_membership_singleton(
        {
            "company_member_count": 2,
            "level": "Corporate Membership",
            "active_memberships": [{"fee": 1, "end_date": d(1)}],
        },
        d(0),
    )
    assert not got


def test_validate_membership_employer_too_few_bad():
    """Singleton corporate memberships fail validation"""
    got = f.Commands()._validate_membership_singleton(
        {
            "cid": "123",
            "company_member_count": 1,
            "level": "Corporate Membership",
            "active_memberships": [{"fee": 1, "end_date": d(1)}],
        },
        d(0),
    )
    assert got == ["Missing required 2+ members in company #123"]


def test_init_new_memberships(mocker, cli):
    """Test init_new_memberships"""
    mocker.patch.object(neon, "get_new_members_needing_setup", return_value=[])
    got = cli("init_new_memberships", ["--apply"])
    assert not got


def test_init_new_memberships_e2e(mocker, cli):
    mocker.patch.object(
        neon,
        "get_new_members_needing_setup",
        return_value=[{"Account ID": "123", "First Name": "Foo", "Email 1": "a@b.com"}],
    )
    m1 = mocker.patch.object(f.memauto, "try_cached_coupon", return_value="test_coupon")
    m2 = mocker.patch.object(
        neon,
        "set_membership_date_range",
        return_value=mocker.MagicMock(status_code=200),
    )
    mocker.patch.object(
        neon,
        "fetch_memberships",
        return_value=[
            {"termStartDate": d(0).isoformat(), "id": "456", "name": "testname"}
        ],
    )

    m3 = mocker.patch.object(
        neon,
        "update_account_automation_run_status",
        return_value=mocker.MagicMock(status_code=200),
    )
    mocker.patch.object(f.memauto, "get_config", return_value=None)
    mocker.patch.object(f.memauto, "get_sample_classes", return_value=[])
    got = cli("init_new_memberships", ["--apply"])
    m1.assert_called_with(75, "a@b.com", True)
    m2.assert_called_with("456", mocker.ANY, mocker.ANY)
    m3.assert_called_with("123", "deferred")


def test_init_new_memberships_limit(mocker, cli):
    mocker.patch.object(
        neon,
        "get_new_members_needing_setup",
        return_value=[
            {"Account ID": str(i), "First Name": "Foo", "Email 1": "a@b.com"}
            for i in range(5)
        ],
    )
    m1 = mocker.patch.object(
        f.memauto.neon,
        "get_latest_membership_id_and_name",
        return_value=("123", "General"),
    )
    m2 = mocker.patch.object(f.memauto, "init_membership", return_value=[])
    got = cli("init_new_memberships", ["--apply", "--limit=2"])
    assert got == []
    m1.assert_has_calls(
        [
            mocker.call("0"),
            mocker.call("1"),
        ]
    )


def test_refresh_volunteer_memberships(mocker, cli):
    """Test refresh_volunteer_memberships command"""
    mocker.patch.object(f, "tznow", return_value=d(0))
    mocker.patch.object(
        f.neon,
        "get_members_with_role",
        side_effect=[
            [
                {
                    "Account ID": 123,
                    "First Name": "John",
                    "Last Name": "Doe",
                }
            ],
            [
                {
                    "Account ID": 456,
                    "First Name": "Jane",
                    "Last Name": "Doe",
                }
            ],
            [
                {
                    "Account ID": 789,
                    "First Name": "Jorb",
                    "Last Name": "Dorb",
                },
                {
                    "Account ID": 999,
                    "First Name": "Past",
                    "Last Name": "DeLimit",
                },
            ],
        ],
    )
    mocker.patch.object(f.Commands, "_last_expiring_membership", return_value=d(0, 23))
    mocker.patch.object(f.neon, "create_zero_cost_membership", return_value={"id": 456})

    got = cli("refresh_volunteer_memberships", ["--apply", "--limit", "3"])
    assert len(got) == 1
    assert got[0]["target"] == "#membership-automation"
    assert got[0]["body"] == MatchStr("new Shop Tech membership")
    assert got[0]["body"] == MatchStr("new Software Dev membership")
    f.neon.create_zero_cost_membership.assert_has_calls(
        [
            mocker.call(
                123,
                d(1, 23),
                d(31, 23),
                level={"id": mocker.ANY, "name": "Shop Tech"},
                term={"id": mocker.ANY, "name": "Shop Tech"},
            ),
            mocker.call(
                456,
                d(1, 23),
                d(31, 23),
                level={"id": mocker.ANY, "name": "Shop Tech"},
                term={"id": mocker.ANY, "name": "Shop Tech"},
            ),
            mocker.call(
                789,
                d(1, 23),
                d(31, 23),
                level={"id": mocker.ANY, "name": "Software Developer"},
                term={"id": mocker.ANY, "name": "Software Developer"},
            ),
        ]
    )


def test_refresh_volunteer_memberships_no_latest_membership(mocker, cli):
    """Test refresh_volunteer_memberships command"""
    mocker.patch.object(f, "tznow", return_value=d(0))
    mocker.patch.object(
        f.neon,
        "get_members_with_role",
        side_effect=[
            [
                {
                    "Account ID": 123,
                    "First Name": "John",
                    "Last Name": "Doe",
                }
            ],
            [],
            [],
        ],
    )
    mocker.patch.object(f.Commands, "_last_expiring_membership", return_value=None)
    mocker.patch.object(f.neon, "create_zero_cost_membership", return_value={"id": 456})

    got = cli("refresh_volunteer_memberships", ["--apply"])
    assert len(got) == 1
    assert got[0]["target"] == "#membership-automation"
    assert got[0]["body"] == MatchStr("new Shop Tech Lead membership")

    f.neon.create_zero_cost_membership.assert_has_calls(
        [
            mocker.call(
                123,
                d(1, 0),
                d(31, 0),
                level={"id": mocker.ANY, "name": "Shop Tech"},
                term={"id": mocker.ANY, "name": "Shop Tech"},
            ),
        ]
    )
