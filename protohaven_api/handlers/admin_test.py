"""Test functions for the admin pages"""

import pytest

from protohaven_api.handlers import admin as a
from protohaven_api.main import app
from protohaven_api.rbac import Role


@pytest.fixture(name="client")
def fixture_client():
    """Provide a test client"""
    return app.test_client()


NEW_MEMBERSHIP_WEBHOOK_DATA = {
    "data": {
        "membership": {
            "membershipId": 134,
            "accountId": 123958,
            "membershipTerm": {
                "termInfo": {"id": 505, "name": "320 individual group 1"},
                "isParentTerm": True,
            },
            "source": {"id": 51, "name": "Your Custom Selection"},
            "customFieldDataList": "",
            "membershipName": "320 individual group 1",
            "termDuration": "1YEAR",
            "fee": 360,
            "transactionDate": "2013-02-17T00:00:00.000-06:00",
            "termStartDate": "2023-09-01-05:00",
            "termEndDate": "2024-08-31-05:00",
            "enrollmentType": "JOIN",
            "status": "Succeed",
            "transaction": {},
        }
    },
    "customParameters": {},
}


def test_neon_new_membership_callback(mocker, client):
    """Test the flow where the user is new with a single membership"""
    mocker.patch.object(
        a,
        "get_config",
        return_value={"neon": {"webhooks": {"new_membership": {"enabled": False}}}},
    )
    mocker.patch.object(a, "roles_from_api_key", return_value=[Role.ADMIN])
    mock_fetch_memberships = mocker.patch.object(
        a.neon, "fetch_memberships", return_value=[{"membershipId": 1}]
    )
    mock_get_account_first_name = mocker.patch.object(
        a, "get_account_first_name", return_value=("John", None, "a@b.com")
    )
    mock_init_membership = mocker.patch.object(
        a.memauto,
        "init_membership",
        return_value=mocker.Mock(subject="subj", body="body", html=True),
    )
    mock_send_email = mocker.patch.object(a.comms, "send_email")
    mock_log_comms = mocker.patch.object(a.airtable, "log_comms")

    rep = client.post(
        "/admin/neon_membership_created_callback", json=NEW_MEMBERSHIP_WEBHOOK_DATA
    )
    assert rep.status_code == 200
    mock_fetch_memberships.assert_called_once_with(123958)
    mock_get_account_first_name.assert_called_once_with(123958)
    mock_init_membership.assert_called_once_with(123958, "John")
    mock_send_email.assert_called_once_with("subj", "body", "a@b.com", True)
    mock_log_comms.assert_called_once_with(
        "neon_new_member_webhook", "a@b.com", "subj", "Sent"
    )