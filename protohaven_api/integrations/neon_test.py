"""Tests for NeonOne integration methods"""
# pylint: skip-file
import datetime
import json

import pytest
from flask import Response

from protohaven_api.config import tznow
from protohaven_api.integrations import neon as n
from protohaven_api.rbac import Role
from protohaven_api.testing import d

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
            mocker.ANY,
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
    m.assert_called_with(1324, (mocker.ANY, [{"name": "TEST", "id": "1234"}]))


def test_set_tech_custom_fields(mocker):
    m = mocker.patch.object(n.neon_base, "set_custom_fields")
    n.set_tech_custom_fields("13245", interest="doing things")
    m.assert_called_with("13245", (148, "doing things"))


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


def test_account_cache_case_insensitive(mocker):
    """Confirm that lookups are case insensitive, and that non-string
    types are handled safely"""
    mocker.patch.object(n, "get_inactive_members", return_value=[])
    want1 = {"Email 1": "aSdF", "Account ID": 123}
    mocker.patch.object(n, "get_active_members", return_value=[want1])
    c = n.AccountCache()
    c.refresh()
    c["gHjK"] = "test"
    c[None] = "foo"
    assert c["AsDf"][123] == want1
    assert c["GhJk"] == "test"
    assert c.get("GhJk") == "test"
    assert c["nonE"] == "foo"
