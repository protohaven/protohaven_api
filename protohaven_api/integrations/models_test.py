"""Various objects representing physical and digital entities."""
from collections import namedtuple

import pytest

from protohaven_api.integrations.models import Event, Member, Role
from protohaven_api.testing import d, idfn


def test_from_neon_fetch():
    """Test Member.from_neon_fetch with valid and empty data"""
    data = {"individualAccount": {"accountId": "123"}}
    m = Member.from_neon_fetch(data)
    assert m.neon_raw_data == data
    assert Member.from_neon_fetch(None) is None


def test_from_neon_search():
    """Test Member.from_neon_search with valid and empty data"""
    data = {"Account ID": "123", "First Name": "Test"}
    m = Member.from_neon_search(data)
    assert m.neon_search_data == data
    assert Member.from_neon_search(None) is None


def test_is_company():
    """Test Member.is_company for company and individual accounts"""
    company_data = {"companyAccount": {"account_id": "foo"}}
    m = Member(neon_raw_data=company_data)
    assert m.is_company()
    m.neon_raw_data = {"individualAccount": {"account_id": "foo"}}
    assert not m.is_company()


def test_fname():
    """Test Member.fname property"""
    data = {"individualAccount": {"primaryContact": {"firstName": "Test"}}}
    m = Member(neon_raw_data=data)
    assert m.fname == "Test"


def test_lname():
    """Test Member.lname property"""
    data = {"individualAccount": {"primaryContact": {"lastName": "Test"}}}
    m = Member(neon_raw_data=data)
    assert m.lname == "Test"


Tc = namedtuple("TC", "desc,first,preferred,last,pronouns,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("basic", "first", "preferred", "last", "a/b", "preferred last (a/b)"),
        Tc("no pronouns or preferred", "first", "", "last", "", "first last"),
        Tc("preferred is last name", "first", "last", "last", "", "last"),
        Tc("only first name", "first", None, None, None, "first"),
    ],
    ids=idfn,
)
def test_name(tc):
    """Confirm expected behavior of nickname resolution from Neon data"""
    search_data = {
        "First Name": tc.first,
        "Preferred Name": tc.preferred,
        "Last Name": tc.last,
        "Pronouns": tc.pronouns,
    }
    m = Member(neon_search_data=search_data)
    assert m.name == tc.want


def test_email():
    """Test Member.email property"""
    data = {
        "individualAccount": {
            "primaryContact": {"email1": "one@test.com", "email2": "two@test.com"}
        }
    }
    m = Member(neon_raw_data=data)
    assert m.email == "one@test.com"
    data["individualAccount"]["primaryContact"]["email1"] = None
    assert m.email == "two@test.com"


def test_zero_cost_ok_until():
    """Test zero_cost_ok_until property with valid and invalid dates"""
    m = Member(
        neon_raw_data={
            "individualAccount": {
                "accountCustomFields": [
                    {
                        "name": "Zero-Cost Membership OK Until Date",
                        "value": d(1).isoformat(),
                    }
                ]
            }
        }
    )
    assert m.zero_cost_ok_until == d(1)
    m.neon_raw_data["individualAccount"]["accountCustomFields"][0]["value"] = "invalid"
    assert m.zero_cost_ok_until is None


def test_neon_id():
    """Test neon_id property from both raw and search data"""
    raw_data = {"individualAccount": {"accountId": "123"}}
    search_data = {"Account ID": "456"}
    m = Member.from_neon_fetch(raw_data)
    assert m.neon_id == "123"
    m = Member.from_neon_search(search_data)
    assert m.neon_id == "456"


def test_roles():
    """Test roles property with various input scenarios"""
    # Test with search data containing pipe-separated roles
    member = Member().from_neon_search({"API server role": "Admin|Shop Tech"})
    assert member.roles == [Role.ADMIN, Role.SHOP_TECH]

    # Test with custom field optionValues
    member = Member().from_neon_fetch(
        {
            "individualAccount": {
                "accountCustomFields": [
                    {"name": "API server role", "optionValues": [{"name": "Admin"}]}
                ]
            }
        }
    )
    assert member.roles == [Role.ADMIN]

    # Test with no roles data
    member = Member()
    assert member.roles is None

    # Test with empty search data
    member = Member()
    member.neon_search_data = {"API server role": ""}
    assert member.roles is None

    # Test with invalid role name
    member = Member()
    member.neon_search_data = {"API server role": "invalid|Admin"}
    assert member.roles == [Role.ADMIN]


def test_has_open_seats_below_price():
    """Test ticket quanty is returned if under max price"""
    evt = Event()
    evt.neon_ticket_data = [
        {"name": "Single Registration", "fee": 50, "numberRemaining": 5},
        {"name": "VIP Registration", "fee": 80, "numberRemaining": 2},
    ]
    assert evt.has_open_seats_below_price(100) == 5
    assert evt.has_open_seats_below_price(49) == 0
