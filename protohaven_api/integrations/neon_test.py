"""Tests for NeonOne integration methods"""
# pylint: skip-file
import datetime
import json

import pytest
from flask import Response

from protohaven_api.config import tznow
from protohaven_api.integrations import neon as n
from protohaven_api.rbac import Role
from protohaven_api.testing import Any, d

TEST_USER = 1234


def test_patch_member_role(mocker):
    """Member role patch adds to existing roles"""
    mocker.patch.object(n, "search_member", return_value=[{"Account ID": 1324}])
    mocker.patch.object(
        n.neon_base,
        "get_custom_field",
        return_value=[{"name": "TEST", "id": "1234"}],
    )
    m = mocker.patch.object(n.neon_base, "set_custom_fields")
    n.patch_member_role("a@b.com", Role.INSTRUCTOR, True)
    m.assert_called_with(
        1324,
        (
            Any(),
            [
                {"name": "TEST", "id": "1234"},
                {"name": "Instructor", "id": "75"},
            ],
        ),
    )


def test_patch_member_role_rm(mocker):
    """Member role patch preserves remaining roles"""
    mocker.patch.object(n, "search_member", return_value=[{"Account ID": 1324}])
    mocker.patch.object(
        n.neon_base,
        "get_custom_field",
        return_value=[
            {"name": "TEST", "id": "1234"},
            {"name": "Instructor", "id": "75"},
        ],
    )
    mocker.patch.object(n.neon_base, "get_connector")
    m = mocker.patch.object(n.neon_base, "set_custom_fields")
    n.patch_member_role("a@b.com", Role.INSTRUCTOR, False)
    m.assert_called_with(1324, (Any(), [{"name": "TEST", "id": "1234"}]))


def test_set_tech_custom_fields(mocker):
    m = mocker.patch.object(n.neon_base, "set_custom_fields")
    n.set_tech_custom_fields("13245", interest="doing things")
    m.assert_called_with("13245", (148, "doing things"))


def test_set_clearances_some_non_matching(mocker):
    """Ensure that if some clearances don't fully resolve into codes, the remaining
    clearances are still applied"""
    mocker.patch.object(
        n, "fetch_clearance_codes", return_value=[{"code": "T1", "id": "test_id"}]
    )
    m = mocker.patch.object(n.neon_base, "set_custom_fields")
    n.set_clearances(TEST_USER, ["T1", "T2"])
    m.assert_called_with(TEST_USER, (Any(), [{"id": "test_id"}]))


def test_set_membership_start_date(mocker):
    """Test setting the membership start date for a user"""
    mock_fetch = mocker.patch.object(
        n,
        "fetch_memberships",
        return_value=[
            {"Term Start Date": "2022-01-01T00:00:00Z", "Membership ID": "123"}
        ],
    )
    m = mocker.patch.object(n.neon_base, "patch")
    account_id = "user_123"
    start_date = d(0)
    result = n.set_membership_start_date(account_id, start_date)
    mock_fetch.assert_called_once_with(account_id)
    m.assert_called_once_with(
        Any(), "/memberships/123", {"termStartDate": d(0).strftime("%Y-%m-%d")}
    )


def test_set_membership_start_date_no_latest(mocker):
    """Test setting the membership start date when no latest membership found"""
    mock_fetch = mocker.patch.object(n, "fetch_memberships", return_value=[])
    account_id = "user_123"
    start_date = d(0)
    with pytest.raises(
        RuntimeError, match=f"No latest membership for member {account_id}"
    ):
        n.set_membership_start_date(account_id, start_date)


def test_get_sample_classes_neon(mocker):
    mocker.patch.object(
        n,
        "search_upcoming_events",
        return_value=[
            {
                "Event Web Publish": "Yes",
                "Event Web Register": "Yes",
                "Event ID": "123",
                "Event Name": "Sample Event",
                "Event Capacity": "10",
                "Event Registration Attendee Count": "5",
                "Event Start Date": "2025-01-05",
                "Event Start Time": "15:00:00",
            }
        ],
    )
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
        n,
        "fetch_registrations",
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
