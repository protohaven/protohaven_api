"""Test methods for finance-oriented CLI commands"""
# pylint: skip-file
import datetime

import yaml

from protohaven_api.commands.finances import (
    Commands as C,  # pylint: disable=import-error
)
from protohaven_api.config import tznow  # pylint: disable=import-error
from protohaven_api.integrations import neon  # pylint: disable=import-error
from protohaven_api.testing import d


def test_validate_memberships_empty(mocker):
    """Empty search shoud pass by default"""
    mocker.patch.object(neon, "search_member", return_value=[])
    got = C()._validate_memberships_internal()
    assert not got


def test_validate_membership_amp_ok():
    """Amp member should pass validation if they are marked appropriately for their term"""
    got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
        {
            "level": "General Membership",
            "active_memberships": [{"fee": 1, "level": "General Membership"}],
        }
    )
    assert got == ["Membership General Membership with no end date (infinite duration)"]


def test_validate_membership_zero_cost_roles_ok():
    """Various roles that are $0 memberships should validate OK"""
    for l in ["Shop Tech", "Board Member", "Staff"]:
        got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
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

    got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
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
    got = C()._validate_membership_singleton(
        {
            "cid": "123",
            "company_member_count": 1,
            "level": "Corporate Membership",
            "active_memberships": [{"fee": 1, "end_date": d(1)}],
        },
        d(0),
    )
    assert got == ["Missing required 2+ members in company #123"]


def test_generate_coupon_id():
    """Test that coupons are generated uniquely"""
    got = C()._generate_coupon_id(n=10)
    assert len(got) == 10
    assert C()._generate_coupon_id(n=10) != got


def test_get_sample_classes(mocker):
    """Test fetching of sample classes"""
    mocker.patch.object(
        neon,
        "fetch_published_upcoming_events",
        return_value=[
            {
                "id": 1,
                "startDate": "2023-10-10",
                "startTime": "10:00AM",
                "name": "Class 1",
            },
            {
                "id": 2,
                "startDate": "2023-10-11",
                "startTime": "11:00AM",
                "name": "Class 2",
            },
            {
                "id": 3,
                "startDate": "2023-10-12",
                "startTime": "12:00PM",
                "name": "Class 3",
            },
        ],
    )
    mocker.patch.object(
        C, "_event_is_suggestible", side_effect=[(True, 5), (True, 1), (False, 0)]
    )
    result = C()._get_sample_classes(10)
    assert result == [
        "Tuesday Oct 10, 10AM: Class 1, https://protohaven.org/e/1",
        "Wednesday Oct 11, 11AM: Class 2, https://protohaven.org/e/2 (1 seat left!)",
    ]


def test_init_membership(mocker):
    """Test init_membership"""
    mocker.patch.object(
        neon, "set_membership_start_date", return_value=mocker.Mock(status_code=200)
    )
    mocker.patch.object(
        neon, "create_coupon_code", return_value=mocker.Mock(status_code=200)
    )
    mocker.patch.object(
        neon,
        "update_account_automation_run_status",
        return_value=mocker.Mock(status_code=200),
    )
    mocker.patch.object(C, "_get_sample_classes", return_value=["class1", "class2"])
    # Test with coupon_amount > 0
    subject, body, _ = C()._init_membership("123", "John Doe", 50, apply=True)
    assert subject == "John Doe: your first class is on us!"
    assert "class1" in body


def test_init_membership_no_classes(mocker):
    """Test init_membership without list of classes"""
    mocker.patch.object(
        neon, "set_membership_start_date", return_value=mocker.Mock(status_code=200)
    )
    mocker.patch.object(
        neon, "create_coupon_code", return_value=mocker.Mock(status_code=200)
    )
    mocker.patch.object(
        neon,
        "update_account_automation_run_status",
        return_value=mocker.Mock(status_code=200),
    )
    mocker.patch.object(C, "_get_sample_classes", return_value=[])
    # Test with coupon_amount > 0
    subject, body, _ = C()._init_membership("123", "John Doe", 50, apply=True)
    assert subject == "John Doe: your first class is on us!"
    assert "Here's a couple basic classes" not in body


def test_event_is_suggestible(mocker):
    """Test that suggestible events are returned if under max price"""
    max_price = 100
    tickets = [
        {"name": "Single Registration", "fee": 50, "numberRemaining": 5},
        {"name": "VIP Registration", "fee": 80, "numberRemaining": 2},
    ]
    mocker.patch.object(neon, "fetch_tickets", return_value=tickets)
    result, number_remaining = C()._event_is_suggestible(123, max_price)
    assert result is True
    assert number_remaining == 5


def test_event_is_suggestible_price_too_high(mocker):
    """Test that events aren't returned if they exceed the max_price"""
    max_price = 40
    tickets = [
        {"name": "Single Registration", "fee": 50, "numberRemaining": 3},
    ]
    mocker.patch.object(neon, "fetch_tickets", return_value=tickets)
    result, _ = C()._event_is_suggestible(123, max_price)
    assert result is False


def test_init_new_memberships(mocker, capsys):
    """Test init_new_memberships"""
    mocker.patch.object(neon, "get_new_members_needing_setup", return_value={})
    C().init_new_memberships(["--apply", "--created_after=2024-01-01"])
    got = yaml.safe_load(capsys.readouterr().out.strip())
    assert not got
