"""Test methods for finance-oriented CLI commands"""
import datetime

from protohaven_api.commands.finances import (
    Commands as C,  # pylint: disable=import-error
)
from protohaven_api.config import tz, tznow  # pylint: disable=import-error
from protohaven_api.integrations import neon  # pylint: disable=import-error


def d(i, h=0):
    """Returns a date based on an integer, for testing"""
    return (
        datetime.datetime(year=2025, month=1, day=1)
        + datetime.timedelta(days=i, hours=h)
    ).astimezone(tz)


def test_validate_memberships_empty(mocker):
    """Empty search shoud pass by default"""
    mocker.patch.object(neon, "search_member", return_value=[])
    got = C().validate_memberships_internal([])
    assert not got


def test_validate_membership_amp_ok():
    """Amp member should pass validation if they are marked appropriately for their term"""
    got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
        {
            "level": "General Membership",
            "active_memberships": [{"fee": 1, "level": "General Membership"}],
        }
    )
    assert got == ["Membership General Membership with no end date (infinite duration)"]


def test_validate_membership_zero_cost_roles_ok():
    """Various roles that are $0 memberships should validate OK"""
    for l in ["Shop Tech", "Board Member", "Staff"]:
        got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
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

    got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
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
    got = C().validate_membership_singleton(
        {
            "cid": "123",
            "company_member_count": 1,
            "level": "Corporate Membership",
            "active_memberships": [{"fee": 1, "end_date": d(1)}],
        },
        d(0),
    )
    assert got == ["Missing required 2+ members in company #123"]
