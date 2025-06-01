"""Tests for NeonOne integration methods"""

# pylint: skip-file
import datetime
import json

import pytest
from flask import Response

from protohaven_api.config import tznow
from protohaven_api.integrations import neon as n
from protohaven_api.integrations.models import Role
from protohaven_api.testing import d

TEST_USER = 1234


def test_patch_member_role(mocker):
    """Member role patch adds to existing roles"""
    mocker.patch.object(
        n, "search_members_by_email", return_value=[
            mocker.MagicMock(neon_id=1324, roles=[{"name": "TEST", "id": "1234"}])
         ]
    )
    m = mocker.patch.object(n.neon_base, "set_custom_fields")
    n.patch_member_role("a@b.com", Role.INSTRUCTOR, enabled=True)
    m.assert_called_with(
        1324,
        (
            mocker.ANY,
            [
                {"name": "TEST", "id": "1234"},
                {"name": "Instructor", "id": "75"},
            ],
        ),
    )


def test_patch_member_role_rm(mocker):
    """Member role patch preserves remaining roles"""
    mocker.patch.object(
        n, "search_members_by_email", return_value=[mocker.MagicMock(neon_id=1324,

            roles=[
                {"name": "TEST", "id": "1234"},
                {"name": "Instructor", "id": "75"},
            ]
                                                                     )]
    )
    mocker.patch.object(n.neon_base, "get_connector")
    m = mocker.patch.object(n.neon_base, "set_custom_fields")
    n.patch_member_role("a@b.com", Role.INSTRUCTOR, False)
    m.assert_called_with(1324, (mocker.ANY, [{"name": "TEST", "id": "1234"}]))


def test_set_tech_custom_fields(mocker):
    m = mocker.patch.object(n.neon_base, "set_custom_fields")
    n.set_tech_custom_fields("13245", interest="doing things")
    m.assert_called_with("13245", (148, "doing things"))


def test_get_sample_classes_neon(mocker):
    m = mocker.MagicMock(
        published=True,
        registration=True,
        neon_id=123,
        capacity=10,
        attendee_count=5,
        start_date=d(4, 15),
    )
    m.name = "Sample Event"

    mocker.patch.object(n, "_search_upcoming_events", return_value=[m])
    mocker.patch.object(n, "tznow", return_value=d(0))
    result = n.get_sample_classes(cache_bust=True)
    assert result == [
        {
            "url": "https://protohaven.org/e/123",
            "name": "Sample Event",
            "date": "Jan 5, 3PM",
            "seats_left": 5,
        }
    ]


def test_delete_single_ticket_registration(mocker):
    """Test deleting a single ticket registration."""
    fetch_registrations_mock = mocker.patch.object(
        n.neon_base,
        "paginated_fetch",
        return_value=[
            {"id": "reg1", "tickets": [{"attendees": [{"accountId": "acc123"}]}]},
            {"id": "reg2", "tickets": [{"attendees": [{"accountId": "acc456"}]}]},
        ],
    )
    delete_mock = mocker.patch.object(
        n.neon_base, "delete", return_value=Response("Deleted", status=200)
    )

    # Test successful deletion
    response = n.delete_single_ticket_registration("acc123", "event1")
    assert response.status_code == 200
    delete_mock.assert_called_once_with("api_key3", "/eventRegistrations/reg1")

    # Test registration not found
    response = n.delete_single_ticket_registration("acc789", "event1")
    assert response.status_code == 404
    assert response.data == b"Registration not found for account acc789 in event event1"


def test_account_cache_case_insensitive(mocker):
    """Confirm that lookups are case insensitive, and that non-string
    types are handled safely"""
    mocker.patch.object(n, "search_inactive_members", return_value=[])
    want1 = mocker.MagicMock(
        email="aSdF",
        fname="foo",
        lname="bar",
        neon_id=123,
        account_current_membership_status="Active",
    )
    mocker.patch.object(n, "search_active_members", return_value=[want1])
    mocker.patch.object(n, "search_members_by_email", return_value=[])
    c = n.AccountCache()
    c.refresh()
    want2 = {456: mocker.MagicMock(fname="bar")}
    c["gHjK"] = want2
    want3 = {789: mocker.MagicMock(fname="baz")}
    c[None] = want3
    assert c["AsDf"][123] == want1
    assert c["GhJk"] == want2
    assert c.get("GhJk") == want2
    assert c["nonE"] == want3


def test_find_best_match(mocker):
    """Test find_best_match returns the best matches based on fuzzy ratio."""
    c = n.AccountCache()
    mocker.patch.object(
        n, "search_members_by_email", side_effect=AssertionError("Should never be called")
    )
    c.update(
        mocker.MagicMock(email="a@b.com", fname="Albert", lname="Einstein", neon_id=123)
    )
    c.update(
        mocker.MagicMock(
            email="b@b.com", fname="Albart", lname="Grovinson", neon_id=456
        )
    )
    c.update(
        mocker.MagicMock(email="b@a.com", fname="Dio", lname="Brando", neon_id=789)
    )

    got = [m.neon_id for m in c.find_best_match("Albert", top_n=2)]
    assert got == [123, 456]


def test_account_cache_miss_inactive(mocker):
    """Confirm that inactive memberships trigger a direct lookup to Neon"""
    mocker.patch.object(
        n,
        "search_members_by_email",
        return_value=[
            mocker.MagicMock(
                email="asdf",
                fname="foo",
                lname="bar",
                neon_id=123,
                account_current_membership_status="Active",
            )
        ],
    )
    c = n.AccountCache()
    c.update(
        mocker.MagicMock(
            email="asdf",
            fname="foo",
            lname="bar",
            neon_id=123,
            account_current_membership_status="Inactive",
        )
    )
    assert c.get("asdf")[123].account_current_membership_status == "Active"
    assert c["asdf"][123].account_current_membership_status == "Active"


def test_account_update_causes_cache_hit(mocker):
    """Confirm that a call to update() fills the cache and does not require
    a Neon lookup upon fetch"""
    want = mocker.MagicMock(
        email="asdf",
        fname="foo",
        lname="bar",
        neon_id=123,
        account_current_membership_status="Active",
    )

    mocker.patch.object(
        n, "search_members_by_email", side_effect=AssertionError("should never be called")
    )
    c = n.AccountCache()
    c.update(want)
    assert c.get(want.email) == {123: want}
    assert c[want.email] == {123: want}


def test_account_cache_miss_keyerror(mocker):
    """Confirm that __getitem__ exceptions are suppressed if direct lookup
    succeeds, are thrown if direct lookup also fails"""
    want = mocker.MagicMock(
        email="asdf",
        fname="foo",
        lname="bar",
        neon_id=123,
        account_current_membership_status="Inactive",
    )
    c = n.AccountCache()

    # Exception suppressed and value returned if direct lookup succeeds
    mocker.patch.object(n, "search_members_by_email", return_value=[want])
    assert c["asdf"] == {123: want}

    # Exception thrown if direct lookup also fails
    mocker.patch.object(n, "search_members_by_email", return_value=[])
    with pytest.raises(KeyError):
        c["asdf"]

