"""Tests for NeonOne integration methods"""
# pylint: skip-file
import datetime
import json

import pytest

from protohaven_api.config import tznow
from protohaven_api.integrations import neon
from protohaven_api.rbac import Role
from protohaven_api.testing import Any, d

TEST_USER = 1234


def test_patch_member_role(mocker):
    """Member role patch adds to existing roles"""
    mocker.patch.object(neon, "search_member", return_value=[{"Account ID": 1324}])
    mocker.patch.object(
        neon,
        "fetch_account",
        return_value={
            "individualAccount": {
                "accountCustomFields": [
                    {
                        "id": neon.CustomField.API_SERVER_ROLE,
                        "optionValues": [{"name": "TEST", "id": "1234"}],
                    }
                ]
            }
        },
    )
    mocker.patch.object(neon, "get_connector")
    nrq = neon.get_connector().neon_request
    nrq.return_value = mocker.MagicMock(), None
    neon.patch_member_role("a@b.com", Role.INSTRUCTOR, True)
    nrq.assert_called()
    assert json.loads(nrq.call_args.kwargs["body"])["individualAccount"][
        "accountCustomFields"
    ][0]["optionValues"] == [
        {"name": "TEST", "id": "1234"},
        {"name": "Instructor", "id": "75"},
    ]


def test_patch_member_role_rm(mocker):
    """Member role patch preserves remaining roles"""
    mocker.patch.object(neon, "search_member", return_value=[{"Account ID": 1324}])
    mocker.patch.object(
        neon,
        "fetch_account",
        return_value={
            "individualAccount": {
                "accountCustomFields": [
                    {
                        "id": neon.CustomField.API_SERVER_ROLE,
                        "optionValues": [
                            {"name": "TEST", "id": "1234"},
                            {"name": "Instructor", "id": "75"},
                        ],
                    }
                ]
            }
        },
    )
    mocker.patch.object(neon, "get_connector")
    nrq = neon.get_connector().neon_request
    nrq.return_value = mocker.MagicMock(), None
    neon.patch_member_role("a@b.com", Role.INSTRUCTOR, False)
    nrq.assert_called()
    assert json.loads(nrq.call_args.kwargs["body"])["individualAccount"][
        "accountCustomFields"
    ][0]["optionValues"] == [{"name": "TEST", "id": "1234"}]


def test_set_tech_custom_fields(mocker):
    mocker.patch.object(
        neon, "fetch_account", return_value={"individualAccount": {"AccountId": 12345}}
    )
    mocker.patch.object(neon, "get_connector")
    nrq = neon.get_connector().neon_request
    nrq.return_value = mocker.MagicMock(), None

    neon.set_tech_custom_fields("13245", interest="doing things")

    nrq.assert_called()
    assert json.loads(nrq.call_args.kwargs["body"]) == {
        "individualAccount": {
            "accountCustomFields": [{"id": 148, "value": "doing things"}]
        }
    }


def test_set_clearances_some_non_matching(mocker):
    """Ensure that if some clearances don't fully resolve into codes, the remaining
    clearances are still applied"""
    mocker.patch.object(
        neon, "fetch_clearance_codes", return_value=[{"code": "T1", "id": "test_id"}]
    )
    mocker.patch.object(
        neon,
        "fetch_account",
        return_value={"individualAccount": {"id": TEST_USER}},
    )
    mocker.patch.object(neon, "get_connector")
    nrq = neon.get_connector().neon_request
    nrq.return_value = mocker.MagicMock(), None

    neon.set_clearances(TEST_USER, ["T1", "T2"])
    _, args, kwargs = nrq.mock_calls[0]
    assert kwargs["body"] == json.dumps(
        {
            "individualAccount": {
                "accountCustomFields": [{"id": 75, "optionValues": [{"id": "test_id"}]}]
            }
        }
    )


def test_set_event_scheduled_state(mocker):
    mocker.patch.object(neon, "get_connector")
    nrq = neon.get_connector().neon_request
    nrq.return_value = {"id": "12345"}

    neon.set_event_scheduled_state(12345, scheduled=False)
    _, args, kwargs = nrq.mock_calls[0]
    assert kwargs["body"] == json.dumps(
        {
            "publishEvent": False,
            "enableEventRegistrationForm": False,
            "archived": True,
            "enableWaitListing": False,
        }
    )


def test_set_membership_start_date(mocker):
    """Test setting the membership start date for a user"""
    mock_fetch = mocker.patch.object(
        neon,
        "fetch_memberships",
        return_value=[
            {"Term Start Date": "2022-01-01T00:00:00Z", "Membership ID": "123"}
        ],
    )
    mock_connector = mocker.patch.object(neon, "get_connector")
    user_id = "user_123"
    start_date = d(0)
    result = neon.set_membership_start_date(user_id, start_date)
    mock_fetch.assert_called_once_with(user_id)
    neon.get_connector().neon_request.assert_called_once_with(
        Any(),
        f"{neon.URL_BASE}/memberships/123",
        "PATCH",
        body=json.dumps({"termStartDate": d(0).strftime("%Y-%m-%d")}),
        headers={"content-type": "application/json"},
    )


def test_set_membership_start_date_no_latest(mocker):
    """Test setting the membership start date when no latest membership found"""
    mock_fetch = mocker.patch.object(neon, "fetch_memberships", return_value=[])
    user_id = "user_123"
    start_date = d(0)
    with pytest.raises(
        RuntimeError, match=f"No latest membership for member {user_id}"
    ):
        neon.set_membership_start_date(user_id, start_date)


def test_update_account_automation_run_status(mocker):
    """Test updating automation run status"""
    mocker.patch.object(neon, "tznow", return_value=d(0))
    mock_set_custom_singleton_fields = mocker.patch.object(
        neon, "_set_custom_singleton_fields", return_value=True
    )
    result = neon.update_account_automation_run_status(123, "completed")
    mock_set_custom_singleton_fields.assert_called_once_with(
        123, {neon.CustomField.ACCOUNT_AUTOMATION_RAN: "completed 2025-01-01"}
    )
    assert result


def test_paginated_account_search(mocker):
    """Test paginated account search to ensure all pages are requested and results are aggregated"""
    data = {"query": "test"}
    mock_connector = mocker.patch.object(neon, "get_connector")
    mock_neon_request = mock_connector.return_value.neon_request
    mock_neon_request.side_effect = [
        {"pagination": {"totalPages": 2}, "searchResults": [{"id": 1}]},
        {"pagination": {"totalPages": 2}, "searchResults": [{"id": 2}]},
    ]
    results = list(neon._paginated_search(data))
    assert results == [{"id": 1}, {"id": 2}]
    assert mock_neon_request.call_count == 2


def test_get_sample_classes_neon(mocker):
    mocker.patch.object(
        neon,
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
    mocker.patch.object(neon, "tznow", return_value=d(0))
    result = neon.get_sample_classes(cache_bust=True)
    assert result == [
        {
            "url": "https://protohaven.org/e/123",
            "name": "Sample Event",
            "date": "Jan 5, 3PM",
            "seats_left": 5,
        }
    ]


def test_paginated_account_search_runtime_error(mocker):
    """Test that _paginated_account_search raises RuntimeError when search fails"""
    data = {"query": "test"}
    mock_connector = mocker.patch.object(neon, "get_connector")
    mock_neon_request = mock_connector.return_value.neon_request
    mock_neon_request.side_effect = [
        {"pagination": {"totalPages": 2}, "searchResults": None}
    ]
    with pytest.raises(RuntimeError, match="Search failed"):
        list(neon._paginated_search(data))
