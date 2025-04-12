"""Test functions for the admin pages"""

import pytest

from protohaven_api import rbac
from protohaven_api.handlers import admin as a
from protohaven_api.testing import d, fixture_client  # pylint: disable=unused-import


def test_user_clearances_notifies_discord(mocker, client):
    """Test that changes to user clearances pushed to discord"""
    mocker.patch.object(
        rbac, "is_enabled", return_value=False
    )  # Disable to allow testing
    mocker.patch.object(a.mclearance, "update", return_value=[])
    mocker.patch.object(a.mclearance, "resolve_codes", return_value=[])
    mocker.patch.object(a.comms, "send_discord_message")

    rep = client.patch(
        "/user/clearances",
        data={"emails": "test@example.com", "codes": "CLEAR1,CLEAR2"},
    )
    a.comms.send_discord_message.assert_called_once()  # pylint: disable=no-member
    assert rep.status_code == 200


def test_user_clearances(mocker, client):
    """Test the user_clearances function"""
    mocker.patch.object(
        rbac, "is_enabled", return_value=False
    )  # Disable to allow testing
    mocker.patch.object(
        a.neon,
        "fetch_clearance_codes",
        return_value=[
            {"name": "CLEAR1", "code": "C1", "id": 1},
            {"name": "CLEAR2", "code": "C2", "id": 2},
        ],
    )
    mocker.patch.object(a.comms, "send_discord_message")
    mocker.patch.object(
        a.neon,
        "search_member",
        return_value=[
            {"Account ID": "123", "Company ID": "456", "Clearances": "CLEAR1|CLEAR2"}
        ],
    )
    mocker.patch.object(
        a.airtable, "get_clearance_to_tool_map", return_value={"MWB": ["ABG", "RBP"]}
    )
    mocker.patch.object(a.neon, "set_clearances", return_value="Success")
    mock_notify = mocker.patch.object(a.mqtt, "notify_clearance")

    rep = client.patch(
        "/user/clearances",
        data={"emails": "test@example.com", "codes": "CLEAR1,CLEAR2"},
    )

    assert rep.status_code == 200
    a.neon.set_clearances.assert_called_with(  # pylint: disable=no-member
        "123", {2, 1}, is_company=False
    )
    mock_notify.assert_has_calls(
        [
            mocker.call("123", "CLEAR1", added=True),
            mocker.call("123", "CLEAR2", added=True),
        ],
        any_order=True,
    )


NEW_MEMBERSHIP_WEBHOOK_DATA = {
    "data": {
        "membershipEnrollment": {
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
        },
        "transaction": {
            "transactionStatus": "SUCCEEDED",
        },
    },
    "customParameters": {
        "api_key": "TEST KEY",  # pragma: allowlist secret
    },
}


@pytest.mark.parametrize(
    "field_value,does_init",
    [
        (None, True),  # If not initialized, do so
        ("asdf", False),  # Bail if setup is already done
    ],
)
def test_neon_new_membership_callback(mocker, client, field_value, does_init):
    """Test the flow where the user is new with a single membership"""
    mocker.patch.object(
        a,
        "get_config",
        return_value={"neon": {"webhooks": {"new_membership": {"enabled": False}}}},
    )
    mocker.patch.object(
        a, "roles_from_api_key", return_value=[rbac.Role.AUTOMATION["name"]]
    )
    mock_fetch_memberships = mocker.patch.object(
        a.neon, "fetch_memberships", return_value=[{"membershipId": 1}]
    )
    mocker.patch.object(
        a,
        "_get_account_details",
        return_value={
            "fname": "John",
            "email": "a@b.com",
            "auto_field_value": field_value,
        },
    )
    mock_init_membership = mocker.patch.object(
        a.memauto,
        "init_membership",
        return_value=[mocker.Mock(subject="subj", body="body", html=True)],
    )
    mock_send_email = mocker.patch.object(a.comms, "send_email")
    mock_log_comms = mocker.patch.object(a.airtable, "log_comms")

    rep = client.post(
        "/admin/neon_membership_created_callback", json=NEW_MEMBERSHIP_WEBHOOK_DATA
    )
    if does_init:
        assert (rep.status_code, rep.text) == (200, "ok")
        mock_fetch_memberships.assert_called_once_with(123958)
        mock_init_membership.assert_called_once_with(
            account_id=123958,
            membership_id=134,
            email="a@b.com",
            fname="John",
            is_amp=False,
        )
        mock_send_email.assert_called_once_with("subj", "body", ["a@b.com"], True)
        mock_log_comms.assert_called_once_with(
            "neon_new_member_webhook", "a@b.com", "subj", "Sent"
        )
    else:
        assert (rep.status_code, rep.text) != (200, mocker.ANY)
        mock_init_membership.assert_not_called()
        mock_send_email.assert_not_called()
        mock_log_comms.assert_not_called()


def test_tool_maintenance_submission(mocker, client):
    """Verify behavior of maintenance submissions"""
    data = {
        "reporter": "abc@def.com",
        "tools": ["IRN", "3D1"],
        "status": "GREEN",
        "summary": "Working Normally",
        "detail": "Nothing wrong here",
        "urgent": False,
        "images": ["https://url/image1.png"],
        "create_task": True,
    }

    mocker.patch.object(
        rbac, "is_enabled", return_value=False
    )  # Disable to allow testing
    mocker.patch.object(a.tasks, "add_tool_report_task")
    mocker.patch.object(a.comms, "send_discord_message")
    mocker.patch.object(a.mqtt, "notify_maintenance")

    response = client.post("/admin/maintenance", json=data)
    assert response.status_code == 200
    a.tasks.add_tool_report_task.assert_called_once_with(  # pylint: disable=no-member
        data["tools"],
        data["summary"],
        data["status"],
        data["images"],
        data["reporter"],
        data["urgent"],
    )
    a.comms.send_discord_message.assert_called_once()  # pylint: disable=no-member
    for tool in data["tools"]:
        a.mqtt.notify_maintenance.assert_any_call(  # pylint: disable=no-member
            tool, data["status"], data["summary"]
        )
