"""Various objects representing physical and digital entities."""
from collections import namedtuple

import pytest

from protohaven_api.integrations import models
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
        {
            "id": 123,
            "name": "Single Registration",
            "fee": 50,
            "numberRemaining": 5,
            "maxNumberAvailable": 7,
        },
        {
            "id": 345,
            "name": "VIP Registration",
            "fee": 80,
            "numberRemaining": 2,
            "maxNumberAvailable": 4,
        },
    ]
    assert evt.has_open_seats_below_price(100) == 5
    assert evt.has_open_seats_below_price(49) == 0


def test_latest_membership(mocker):
    """Fetch the latest membership in the member data"""
    member = Member()
    mocker.patch.object(models, "tznow", return_value=d(0))
    member.neon_membership_data = [
        {
            "termStartDate": d(1).isoformat(),
            "id": 123,
            "membershipLevel": {"name": "A"},
        },
        {
            "termStartDate": d(3).isoformat(),
            "id": 456,
            "membershipLevel": {"name": "B"},
        },
        {
            "termStartDate": d(2).isoformat(),
            "id": 789,
            "membershipLevel": {"name": "C"},
        },
    ]
    assert member.latest_membership().neon_id == 456


def test_volunteer_bio_and_picture():
    """Ensure parsing of volunteer airtable data"""
    member = Member()
    member.airtable_bio_data = {
        "fields": {
            "Picture": [{"thumbnails": {"large": {"url": "want"}}}],
            "Bio": "This is a bio",
        },
    }
    assert member.volunteer_bio == "This is a bio"
    assert member.volunteer_picture == "want"

    # Also test Nocodb signed path
    member.airtable_bio_data = {
        "fields": {
            "Picture": [{"thumbnails": {"large": {"signedPath": "abc"}}}],
        },
    }
    assert member.volunteer_picture == "http://localhost:8080/abc"


def test_event_properties():
    """Test all public @property methods of Event class"""
    # Setup test data
    start = d(0, 18)
    end = d(0, 21)
    neon_raw = {
        "id": 123,
        "name": "Test Event",
        "description": "Test Description",
        "maximumAttendees": 10,
        "archived": False,
        "publishEvent": True,
        "enableEventRegistrationForm": True,
        "eventDates": {
            "startDate": start.strftime("%Y-%m-%d"),
            "startTime": start.strftime("%H:00"),
            "endDate": end.strftime("%Y-%m-%d"),
            "endTime": end.strftime("%H:00"),
        },
    }
    neon_search = {
        "Event ID": 123,
        "Event Name": "Test Event",
        "Event Description": "Test Description",
        "Event Capacity": 10,
        "Event Archive": "No",
        "Event Web Publish": "Yes",
        "Event Web Register": "Yes",
        "Event Start Date": start.strftime("%Y-%m-%d"),
        "Event Start Time": start.strftime("%H:00"),
        "Event End Date": end.strftime("%Y-%m-%d"),
        "Event End Time": end.strftime("%H:00"),
        "Event Registration Attendee Count": 1,
    }

    eventbrite = {
        "id": "456",
        "name": {"text": "Test Event"},
        "description": {"html": "Test Description"},
        "capacity": 10,
        "start": {"utc": start.isoformat()},
        "end": {"utc": end.isoformat()},
        "url": "https://example.com",
        "status": "live",
        "listed": True,
        "ticket_classes": [
            {
                "id": 111,
                "name": "General",
                "cost": {"major_value": "10.00"},
                "quantity_total": 10,
                "quantity_sold": 1,
            }
        ],
    }
    airtable = {
        "fields": {
            "Email": "test@example.com",
            "Instructor": "Test Instructor",
            "Supply Cost (from Class)": "10.00",
            "Volunteer": ["Yes"],
            "Supply State": "Ordered",
        }
    }
    attendees = [
        {
            "accountId": 1,
            "registrationStatus": "SUCCEEDED",
            "email": "a@b.com",
            "firstName": "first",
            "lastName": "last",
        }
    ]
    eb_attendees = [
        {
            "id": 1,
            "cancelled": False,
            "refunded": False,
            "profile": {"first_name": "first", "last_name": "last", "email": "a@b.com"},
        }
    ]
    tickets = [
        {
            "id": 111,
            "name": "Single Registration",
            "fee": 10,
            "maxNumberAvailable": 10,
            "numberRemaining": 9,
        }
    ]

    # Test each data source
    for source, data in [
        ("neon_raw", neon_raw),
        ("neon_search", neon_search),
        ("eventbrite", eventbrite),
    ]:
        if source == "neon_raw":
            evt = Event.from_neon_fetch(data)
        elif source == "neon_search":
            evt = Event.from_neon_search(data)
        else:
            evt = Event.from_eventbrite_search(data)

        if "neon" in source:
            evt.set_attendee_data(attendees)
            evt.set_ticket_data(tickets)
        else:
            evt.set_attendee_data(eb_attendees)
        evt.set_airtable_data(airtable)

        # Test properties
        assert evt.neon_id == (123 if source != "eventbrite" else "456")
        assert evt.name == "Test Event"
        assert evt.description
        assert evt.capacity == 10
        assert evt.archived is False
        assert evt.published is True
        assert evt.registration is True
        assert evt.start_date == start
        assert evt.end_date == end
        at = list(evt.attendees)[0]
        assert at.name == "first last"
        assert at.email == "a@b.com"
        assert evt.signups == {1}
        assert list(evt.ticket_options) == [
            {
                "id": 111,
                "name": "Single Registration" if "neon" in source else "General",
                "price": 10,
                "sold": 1,
                "total": 10,
            }
        ]
        assert evt.attendee_count == 1
        assert evt.occupancy == 0.1
        assert evt.in_blocklist is False
        assert evt.has_open_seats_below_price(15) == 9
        assert evt.single_registration_ticket_id == 111
        assert evt.url
        assert evt.instructor_email == "test@example.com"
        assert evt.instructor_name == "Test Instructor"
        assert evt.supply_cost == "10.00"
        assert evt.volunteer == "Yes"
        assert evt.supply == "Ordered"
