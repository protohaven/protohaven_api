"""Test methods for finance-oriented CLI commands"""

# pylint: skip-file
import datetime

import pytest
import yaml

from protohaven_api.commands import finances as f
from protohaven_api.config import tznow  # pylint: disable=import-error
from protohaven_api.integrations import neon  # pylint: disable=import-error
from protohaven_api.rbac import Role
from protohaven_api.testing import MatchStr, d, mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    return mkcli(capsys, f)


def test_transaction_alerts_ok(mocker, cli):
    mocker.patch.object(
        f.sales, "get_customer_name_map", return_value={"cust_id": "Foo Bar"}
    )
    mocker.patch.object(f.sales, "get_unpaid_invoices_by_id", return_value={})
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
        return_value=[
            {
                "status": "ACTIVE",
                "id": "sub_id",
                "plan_variation_id": "var_id",
                "customer_id": "cust_id",
                "charged_through_date": d(0).isoformat(),
                "invoice_ids": [],
            }
        ],
    )
    mocker.patch.object(f.sales, "subscription_tax_pct", return_value=7.0)
    got = cli("transaction_alerts", [])
    assert not got


def test_transaction_alerts_active_with_unpaid_invoice(mocker, cli):
    """ACTIVE subscription with unpaid invoice should raise alert"""
    mocker.patch.object(
        f.sales, "get_customer_name_map", return_value={"cust_id": "Test Customer"}
    )
    mocker.patch.object(
        f.sales,
        "get_subscription_plan_map",
        return_value={"plan_id": ("Test Plan", 1000)},
    )
    mocker.patch.object(
        f.sales, "get_unpaid_invoices_by_id", return_value=[("inv_id", "$10.00")]
    )
    mock_sub = {
        "id": "sub_id",
        "status": "ACTIVE",
        "plan_variation_id": "plan_id",
        "customer_id": "cust_id",
        "invoice_ids": ["inv_id", "inv2_id"],
        "charged_through_date": d(10).isoformat(),
    }
    mocker.patch.object(f.sales, "get_subscriptions", return_value=[mock_sub])
    mocker.patch.object(f.sales, "subscription_tax_pct", return_value=7.0)
    mocker.patch.object(f, "tznow", return_value=d(0))

    got = cli("transaction_alerts", [])

    assert got and len(got) == 1
    assert "charged through 2025-01-11, unpaid [$10.00]" in got[0]["body"]
    assert "inv_id" in got[0]["body"]
    assert "inv2_id" not in got[0]["body"]


def test_validate_memberships_empty(mocker):
    """Empty search shoud pass by default"""
    mocker.patch.object(neon, "search_active_members", return_value=[])
    got = list(f.Commands()._validate_memberships_internal())
    assert not got


def test_validate_membership_amp_ok(mocker):
    """Amp member should pass validation if they are marked appropriately for their term"""
    mem = mocker.Mock(
        fee=1, term="ELI", level="AMP General", start_date=d(0), end_date=d(5)
    )
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                income_based_rate="Extremely Low Income",
                memberships=lambda active_only: [mem],
                latest_membership=lambda active_only: mem,
            ),
            0,
            0,
            d(0),
        )
    )
    assert not got


def test_validate_multi_membership_bad(mocker):
    """All memberships should have an end date"""
    mem = mocker.MagicMock(
        fee=1,
        start_date=d(0),
        end_date=d(5),
        status="SUCCEEDED",
        level="General Membership",
    )
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                level="General Membership",
                memberships=lambda active_only: [mem, mem],
            ),
            0,
            0,
            d(1),
        )
    )
    assert got == ["Multiple active memberships: want 1, got 2"]


def test_validate_multi_membership_future_start_date_ok(mocker):
    """Should be OK with exactly one valid membership even if future memberships exist"""
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                level="General Membership",
                memberships=lambda active_only: [
                    mocker.MagicMock(
                        fee=1,
                        start_date=None,
                        end_date=d(5),
                        status="SUCCEEDED",
                        level="General Membership",
                    ),
                    mocker.MagicMock(
                        fee=1,
                        start_date=d(3),
                        end_date=d(5),
                        status="SUCCEEDED",
                        level="General Membership",
                    ),
                ],
            ),
            0,
            0,
            d(0),
        )
    )
    assert not got


def test_validate_multi_membership_refunded_ok(mocker):
    """Refunded memberships should not count for validation"""
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                level="General Membership",
                memberships=lambda active_only: [
                    mocker.MagicMock(
                        fee=1,
                        start_date=d(0),
                        end_date=d(5),
                        status="SUCCEEDED",
                        level="General Membership",
                    ),
                    mocker.MagicMock(
                        fee=1,
                        start_date=d(0),
                        end_date=d(5),
                        status="REFUNDED",
                        level="General Membership",
                    ),
                ],
            ),
            0,
            0,
            d(0),
        )
    )
    assert not got


def test_validate_membership_no_end_date_bad(mocker):
    """All memberships should have an end date"""
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                level="General Membership",
                memberships=lambda active_only: [
                    mocker.Mock(
                        fee=1,
                        level="General Membership",
                        start_date=d(0),
                        end_date=datetime.datetime.max,
                        status="SUCCEEDED",
                    ),
                ],
            ),
            0,
            0,
            d(0),
        )
    )
    assert got == ["Membership General Membership with no end date (infinite duration)"]


def test_validate_membership_zero_cost_roles_ok(mocker):
    """Various roles that are $0 memberships should validate OK"""
    for l, r in [
        ("Shop Tech", Role.SHOP_TECH),
        ("Board Member", Role.BOARD_MEMBER),
        ("Staff", Role.STAFF),
        ("Software Developer", Role.SOFTWARE_DEV),
    ]:
        got = list(
            f.Commands()._validate_membership_singleton(
                mocker.MagicMock(
                    level=l,
                    roles=[r],
                    memberships=lambda active_only: [
                        mocker.Mock(
                            fee=0,
                            level=l,
                            start_date=d(0),
                            end_date=d(5),
                            status="SUCCEEDED",
                        ),
                    ],
                ),
                0,
                0,
                d(0),
            )
        )
        assert not got


def test_validate_membership_general_zero_cost_bad(mocker):
    """General membership should always cost money, unless explicitly marked"""
    l = "General Membership"
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                level=l,
                zero_cost_ok_until=tznow() - datetime.timedelta(days=1),
                memberships=lambda active_only: [
                    mocker.Mock(
                        fee=0,
                        level=l,
                        start_date=d(0),
                        end_date=d(5),
                        status="SUCCEEDED",
                    ),
                ],
            ),
            0,
            0,
            d(0),
        )
    )
    assert got == [MatchStr("Abnormal zero-cost membership General Membership")]

    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                level=l,
                zero_cost_ok_until=tznow() + datetime.timedelta(days=1),
                memberships=lambda active_only: [
                    mocker.Mock(
                        fee=0,
                        level=l,
                        start_date=d(0),
                        end_date=d(5),
                        status="SUCCEEDED",
                    ),
                ],
            ),
            0,
            0,
            d(0),
        )
    )
    assert not got


def test_validate_membership_instructor_ok(mocker):
    """Instructor should validate when role is applied"""
    l = "Instructor"
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                level=l,
                roles=[Role.INSTRUCTOR],
                memberships=lambda active_only: [
                    mocker.Mock(
                        fee=1,
                        level=l,
                        start_date=d(0),
                        end_date=d(5),
                        status="SUCCEEDED",
                    ),
                ],
            ),
            0,
            0,
            d(0),
        )
    )
    assert not got


def test_validate_membership_instructor_no_role(mocker):
    """Raise validation error for instructor without role"""
    l = "Instructor"
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                level=l,
                roles=[],
                memberships=lambda active_only: [
                    mocker.Mock(
                        fee=1,
                        level=l,
                        start_date=d(0),
                        end_date=d(5),
                        status="SUCCEEDED",
                    ),
                ],
            ),
            0,
            0,
            d(0),
        )
    )
    assert got == ["Needs role Instructor, has none"]


def test_validate_membership_addl_family_ok(mocker):
    """Conforming additional family member"""
    l = "Additional Family Membership"
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                household_id=1234,
                level=l,
                memberships=lambda active_only: [
                    mocker.Mock(
                        fee=1,
                        level=l,
                        start_date=d(0),
                        end_date=d(5),
                        status="SUCCEEDED",
                    ),
                ],
            ),
            1,
            0,
            d(0),
        )
    )
    assert not got


@pytest.mark.parametrize("paying_member_count", [1, 0])
def test_validate_membership_addl_family_no_fullprice_bad(mocker, paying_member_count):
    """Addl membership without a paid membership in the household is a no-no"""
    l = "Additional Family Membership"
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                household_id=1234,
                level=l,
                memberships=lambda active_only: [
                    mocker.Mock(
                        fee=1,
                        level=l,
                        start_date=d(0),
                        end_date=d(5),
                        status="SUCCEEDED",
                    ),
                ],
            ),
            paying_member_count,
            0,
            d(0),
        )
    )
    if paying_member_count == 0:
        assert got == [
            "Missing required non-additional paid member in household [#1234](https://protohaven.app.neoncrm.com/np/admin/account/householdDetails.do?householdId=1234)"
        ]
    else:
        assert not got


@pytest.mark.parametrize("company_member_count", [2, 1])
def test_validate_membership_employer(mocker, company_member_count):
    """Corporate memberships with two members are OK, but one fails validation"""
    l = "Company Membership"
    got = list(
        f.Commands()._validate_membership_singleton(
            mocker.MagicMock(
                company_id=1234,
                level=l,
                memberships=lambda active_only: [
                    mocker.Mock(
                        fee=1,
                        level=l,
                        start_date=d(0),
                        end_date=d(5),
                        status="SUCCEEDED",
                    ),
                ],
            ),
            0,
            company_member_count,
            d(0),
        )
    )
    if company_member_count > 1:
        assert not got
    else:
        assert got == [
            "Missing required 2+ members in company [#1234](https://protohaven.app.neoncrm.com/admin/accounts/1234)"
        ]


def test_init_new_memberships(mocker, cli):
    """Test init_new_memberships"""
    mocker.patch.object(neon, "search_new_members_needing_setup", return_value=[])
    got = cli("init_new_memberships", ["--apply"])
    assert not got


def test_init_new_memberships_e2e(mocker, cli):
    mocker.patch.object(
        neon,
        "search_new_members_needing_setup",
        return_value=[
            mocker.MagicMock(
                neon_id=123,
                fname="Foo",
                email="a@b.com",
                latest_membership=lambda successful_only: mocker.MagicMock(
                    start_date=d(0), neon_id=456, level="testname"
                ),
            )
        ],
    )
    m1 = mocker.patch.object(f.memauto, "try_cached_coupon", return_value="test_coupon")
    m2 = mocker.patch.object(
        neon,
        "set_membership_date_range",
        return_value=mocker.MagicMock(status_code=200),
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
    m2.assert_called_with(456, mocker.ANY, mocker.ANY)
    m3.assert_called_with(123, "deferred")


def test_init_new_memberships_limit(mocker, cli):
    """--limit is observed in invocation"""
    mocker.patch.object(
        neon,
        "search_new_members_needing_setup",
        return_value=[mocker.MagicMock(neon_id=i) for i in range(5)],
    )

    m2 = mocker.patch.object(f.memauto, "init_membership", return_value=[])
    got = cli("init_new_memberships", ["--apply", "--limit=2"])
    assert got == []
    assert len(m2.mock_calls) == 2


def test_refresh_volunteer_memberships(mocker, cli):
    """Test refresh_volunteer_memberships command"""
    mocker.patch.object(f, "tznow", return_value=d(0))
    ld = (d(0, 23), False)
    mocker.patch.object(
        f.neon,
        "search_members_with_role",
        side_effect=[
            [
                mocker.MagicMock(
                    neon_id=123,
                    fname="John",
                    lname="Doe",
                    last_membership_expiration_date=lambda: ld,
                )
            ],
            [
                mocker.MagicMock(
                    neon_id=456,
                    fname="Jane",
                    lname="Doe",
                    last_membership_expiration_date=lambda: ld,
                )
            ],
            [
                mocker.MagicMock(
                    neon_id=789,
                    fname="Jorb",
                    lname="Dorb",
                    last_membership_expiration_date=lambda: ld,
                ),
                mocker.MagicMock(
                    neon_id=999,
                    fname="Past",
                    lname="DeLimit",
                    last_membership_expiration_date=lambda: ld,
                ),
            ],
        ],
    )
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
        "search_members_with_role",
        side_effect=[
            [
                mocker.MagicMock(
                    neon_id=123,
                    fname="John",
                    lname="Doe",
                    last_membership_expiration_date=lambda: (None, None),
                )
            ],
            [],
            [],
        ],
    )
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


def test_refresh_volunteer_memberships_autorenew(mocker, cli):
    """Test refresh_volunteer_memberships command"""
    mocker.patch.object(f, "tznow", return_value=d(0))
    mocker.patch.object(
        f.neon,
        "search_members_with_role",
        side_effect=[
            [
                mocker.MagicMock(
                    neon_id=123,
                    fname="John",
                    lname="Doe",
                    last_membership_expiration_date=lambda: (None, True),
                )
            ],
            [],
            [],
        ],
    )
    mocker.patch.object(f.neon, "create_zero_cost_membership")

    got = cli("refresh_volunteer_memberships", ["--apply"])
    assert not got
    f.neon.create_zero_cost_membership.assert_not_called()


def test_refresh_volunteer_memberships_exclude(mocker, cli):
    """Test refresh_volunteer_memberships command"""
    mocker.patch.object(f, "tznow", return_value=d(0))
    mocker.patch.object(
        f.neon,
        "search_members_with_role",
        side_effect=[
            [
                mocker.MagicMock(
                    neon_id=123,
                    fname="John",
                    lname="Doe",
                    last_membership_expiration_date=lambda: (None, None),
                )
            ],
            [],
            [],
        ],
    )
    mocker.patch.object(f.neon, "create_zero_cost_membership", return_value={"id": 456})

    got = cli("refresh_volunteer_memberships", ["--apply", "--exclude=123"])
    assert not got
    f.neon.create_zero_cost_membership.assert_not_called()


def test_refresh_volunteer_memberships_filter_dev(mocker, cli):
    """Test refresh_volunteer_memberships command"""
    mocker.patch.object(f, "tznow", return_value=d(0))
    mocker.patch.object(
        f.neon,
        "search_members_with_role",
        side_effect=[
            [],
            [],
            [  # Dev comes last
                mocker.MagicMock(
                    neon_id=123,
                    fname="John",
                    lname="Doe",
                    last_membership_expiration_date=lambda: (None, None),
                )
            ],
        ],
    )
    mocker.patch.object(f.neon, "create_zero_cost_membership", return_value={"id": 456})

    got = cli("refresh_volunteer_memberships", ["--apply", "--filter_dev=456"])
    assert not got
    f.neon.create_zero_cost_membership.assert_not_called()
