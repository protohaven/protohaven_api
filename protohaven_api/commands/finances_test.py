"""Test methods for finance-oriented CLI commands"""
# pylint: skip-file
import datetime

import pytest
import yaml
from dateutil import parser as dateparser

from protohaven_api.commands import finances as f
from protohaven_api.config import tznow  # pylint: disable=import-error
from protohaven_api.integrations import neon  # pylint: disable=import-error
from protohaven_api.testing import Any, d, mkcli


@pytest.fixture
def cli(capsys):
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
    got = f.Commands()._validate_memberships_internal()
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
    for l in ["Shop Tech", "Board Member", "Staff"]:
        got = f.Commands()._validate_membership_singleton(
            {
                "level": l,
                "roles": [l],
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
    assert got == ["Abnormal zero-cost membership General Membership"]

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
    got = cli("init_new_memberships", ["--apply", "--created_after=2024-01-01"])
    assert not got


def test_init_new_memberships_e2e(mocker, cli):
    mocker.patch.object(
        neon,
        "get_new_members_needing_setup",
        return_value=[{"Account ID": "123", "First Name": "Foo", "Email 1": "a@b.com"}],
    )
    mocker.patch.object(
        neon, "create_coupon_code", return_value=mocker.MagicMock(status_code=200)
    )
    mocker.patch.object(
        neon,
        "set_membership_start_date",
        return_value=mocker.MagicMock(status_code=200),
    )
    mocker.patch.object(
        neon,
        "update_account_automation_run_status",
        return_value=mocker.MagicMock(status_code=200),
    )
    mocker.patch.object(f.memauto, "get_sample_classes", return_value=[])
    got = cli("init_new_memberships", ["--apply", "--created_after=2024-01-01"])
    neon.set_membership_start_date.assert_called_with("123", Any())
    neon.create_coupon_code.assert_called_with(Any(), 75)
    neon.update_account_automation_run_status.assert_called_with("123", "deferred")
