"""Verify proper behavior of public access pages"""
# pylint: skip-file
import json

import pytest

from protohaven_api.handlers import index
from protohaven_api.integrations import neon
from protohaven_api.main import app
from protohaven_api.rbac import set_rbac
from protohaven_api.testing import Any, MatchStr


@pytest.fixture()
def client():
    return app.test_client()


def _setup_session(client):
    with client.session_transaction() as session:
        session["neon_id"] = 1234
        session["neon_account"] = {
            "individualAccount": {
                "accountCustomFields": [],
                "primaryContact": {
                    "firstName": "First",
                    "lastName": "Last",
                    "email1": "foo@bar.com",
                },
            }
        }


def test_index(client):
    """Test behavior of index page"""
    _setup_session(client)
    response = client.get("/")
    assert "Protohaven Dashboard" in response.data.decode("utf8")


def test_whoami(client):
    """test /whoami returns session info"""
    _setup_session(client)
    response = client.get("/whoami")
    assert json.loads(response.data.decode("utf8")) == {
        "fullname": "First Last",
        "email": "foo@bar.com",
    }


def test_welcome_signin_get(client, mocker):
    """Check that the svelte page is loaded"""
    mocker.patch.object(app, "send_static_file", return_value="TEST")
    assert "TEST" == client.get("/welcome").data.decode("utf8")
    app.send_static_file.assert_called_with("svelte/index.html")


def test_welcome_signin_guest_no_referrer(mocker):
    """Guest data with no referrer is omitted from form submission"""
    mocker.patch.object(index, "submit_google_form")
    ws = mocker.MagicMock()
    ws.receive.return_value = json.dumps({"person": "guest", "waiver_ack": True})
    index.welcome_sock(ws)
    rep = json.loads(ws.send.mock_calls[-1].args[0])
    assert rep["waiver_signed"] == True
    index.submit_google_form.assert_not_called()


def test_welcome_signin_guest_referrer(mocker):
    """Guest sign in with referrer data is submitted"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index.airtable, "insert_signin")
    ws = mocker.MagicMock()
    ws.receive.return_value = json.dumps(
        {
            "person": "guest",
            "waiver_ack": True,
            "referrer": "TEST",
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        }
    )
    index.welcome_sock(ws)
    index.submit_google_form.assert_called_once_with(
        "signin",
        {
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
            "waiver_ack": (
                "I have read and understand this agreement and agree to be bound by its requirements.",
            ),
            "referrer": "TEST",
            "purpose": "I'm a member, just signing in!",
            "am_member": "No",
        },
    )
    index.airtable.insert_signin.assert_called()


def test_welcome_signin_notfound(mocker):
    """Ensure form does not get called if member not found"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index, "neon")
    index.neon.search_member.return_value = []
    ws = mocker.MagicMock()
    ws.receive.return_value = json.dumps(
        {
            "person": "member",
            "waiver_ack": True,
            "referrer": "TEST",
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        }
    )
    index.welcome_sock(ws)
    rep = json.loads(ws.send.mock_calls[-1].args[0])
    assert rep == {
        "announcements": [],
        "firstname": "member",
        "notfound": True,
        "status": False,
        "violations": [],
        "waiver_signed": False,
    }
    index.submit_google_form.assert_not_called()


def test_welcome_signin_membership_expired(mocker):
    """Ensure form submits and proper status returns on expired membership"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index.airtable, "insert_signin")
    mocker.patch.object(index, "neon")
    mocker.patch.object(index, "airtable")
    mocker.patch.object(index, "send_membership_automation_message")
    index.neon.search_member.return_value = [
        {
            "Account ID": 12345,
            "Account Current Membership Status": "Inactive",
            "First Name": "First",
            "API server role": None,  # This can happen
        }
    ]
    index.airtable.get_announcements_after.return_value = []
    index.neon.update_waiver_status.return_value = True
    ws = mocker.MagicMock()
    ws.receive.return_value = json.dumps(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    index.welcome_sock(ws)
    rep = json.loads(ws.send.mock_calls[-1].args[0])
    assert rep["status"] == "Inactive"
    index.submit_google_form.assert_called()  # Form submission even if membership is expired
    index.airtable.insert_signin.assert_called()
    index.send_membership_automation_message.assert_called_with(
        "[First (foo@bar.com)](https://protohaven.app.neoncrm.com/admin/accounts/12345) just signed in at the front desk but has a non-Active membership status in Neon: status is Inactive ([wiki](https://protohaven.org/wiki/software/membership_validation))\n"
    )


def test_welcome_signin_ok_with_violations(mocker):
    """Test that form submission triggers and announcements are returned when OK member logs in"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index, "neon")
    mocker.patch.object(index, "airtable")
    mocker.patch.object(index, "send_membership_automation_message")
    index.neon.search_member.return_value = [
        {
            "Account ID": 12345,
            "Account Current Membership Status": "Active",
            "First Name": "First",
        }
    ]
    index.airtable.get_policy_violations.return_value = [
        {"fields": {"Neon ID": "Someone else"}},
        {"fields": {"Neon ID": "12345", "Closure": "2024-04-01 00:00"}},
        {"fields": {"Neon ID": "12345", "Notes": "This one is shown"}},
    ]
    index.airtable.get_announcements_after.return_value = []
    index.neon.update_waiver_status.return_value = True
    ws = mocker.MagicMock()
    ws.receive.return_value = json.dumps(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    index.welcome_sock(ws)
    rep = json.loads(ws.send.mock_calls[-1].args[0])
    assert rep["violations"] == [
        {"fields": {"Neon ID": "12345", "Notes": "This one is shown"}}
    ]
    index.send_membership_automation_message.assert_called_with(
        "[First (foo@bar.com)](https://protohaven.app.neoncrm.com/admin/accounts/12345) just signed in at the front desk with violations: `[{'fields': {'Neon ID': '12345', 'Notes': 'This one is shown'}}]` ([wiki](https://protohaven.org/wiki/software/membership_validation))\n"
    )


def test_welcome_signin_ok_with_duplicates(mocker):
    """Test that form submission triggers and a discord notification is sent if there's duplicate accounts"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index, "neon")
    mocker.patch.object(index, "airtable")
    mocker.patch.object(index, "send_membership_automation_message")
    index.neon.search_member.return_value = [
        {
            "Account ID": 12346,  # Extra membership, makes things ambiguous
        },
        {
            "Account ID": 12345,
            "Account Current Membership Status": "Active",
            "First Name": "First",
            "API server role": "Shop Tech",
        },
    ]
    index.airtable.get_announcements_after.return_value = []
    index.neon.update_waiver_status.return_value = True
    ws = mocker.MagicMock()
    ws.receive.return_value = json.dumps(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    index.welcome_sock(ws)
    rep = json.loads(ws.send.mock_calls[-1].args[0])
    assert rep["status"] == "Active"
    index.send_membership_automation_message.mock_calls[0].args[0].startswith(
        "Sign-in with foo@bar.com returned multiple accounts in Neon with same email"
    )


def test_welcome_signin_ok_with_announcements(mocker):
    """Test that form submission triggers and announcements are returned when OK member logs in"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index, "neon")
    mocker.patch.object(index, "airtable")
    index.neon.search_member.return_value = [
        {
            "Account ID": 12345,
            "Account Current Membership Status": "Active",
            "First Name": "First",
            "API server role": "Shop Tech",
        }
    ]
    index.airtable.get_announcements_after.return_value = [
        {"Title": "Test Announcement"}
    ]
    index.neon.update_waiver_status.return_value = True
    ws = mocker.MagicMock()
    ws.receive.return_value = json.dumps(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    index.welcome_sock(ws)
    rep = json.loads(ws.send.mock_calls[-1].args[0])
    _, args, _ = index.airtable.get_announcements_after.mock_calls[0]
    assert args[1] == ["Shop Tech", "Member"]
    assert rep["status"] == "Active"
    assert rep["announcements"] == [{"Title": "Test Announcement"}]
    index.submit_google_form.assert_called_with(
        "signin",
        {
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
            "waiver_ack": (
                "I have read and understand this agreement and agree to be bound by its requirements.",
            ),
            "referrer": None,
            "purpose": "I'm a member, just signing in!",
            "am_member": "Yes",
        },
    )
    index.airtable.insert_signin.assert_called()


def test_welcome_signin_ok_with_company_id(mocker):
    """Test that form submission triggers and a discord notification is sent if there's duplicate accounts"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index, "neon")
    mocker.patch.object(index, "airtable")
    mocker.patch.object(index, "send_membership_automation_message")
    index.neon.search_member.return_value = [
        {
            "Account ID": 12346,
            "Company ID": 12346,  # Matches account ID, so ignored
        },
        {
            "Account ID": 12345,
            "Company ID": 12346,
            "Account Current Membership Status": "Active",
            "First Name": "First",
            "API server role": "Shop Tech",
        },
    ]
    index.airtable.get_announcements_after.return_value = []
    index.neon.update_waiver_status.return_value = True
    ws = mocker.MagicMock()
    ws.receive.return_value = json.dumps(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    index.welcome_sock(ws)
    rep = json.loads(ws.send.mock_calls[-1].args[0])
    assert rep["status"] == "Active"
    index.send_membership_automation_message.assert_not_called()


def test_welcome_signin_with_notify_board_and_staff(mocker):
    """Test that a discord notification is sent if the account is flagged"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index, "neon")
    mocker.patch.object(index, "airtable")
    mocker.patch.object(index, "send_membership_automation_message")
    index.neon.search_member.return_value = [
        {
            "Account ID": 12345,
            "Account Current Membership Status": "Active",
            "First Name": "First",
            "Notify Board & Staff": "On Sign In|Other Unrelated Condition",
        },
    ]
    index.airtable.get_announcements_after.return_value = []
    index.neon.update_waiver_status.return_value = True
    ws = mocker.MagicMock()
    ws.receive.return_value = json.dumps(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    index.welcome_sock(ws)
    index.send_membership_automation_message.assert_called_with(
        "@Board and @Staff: [First (foo@bar.com)](https://protohaven.app.neoncrm.com/admin/accounts/12345) just signed in at the front desk with `Notify Board & Staff = On Sign In`. This indicator suggests immediate followup with this member is needed. Click the name/email link for notes in Neon CRM."
    )


def test_get_or_activate_multiple_accounts(mocker):
    """Test if multiple accounts are found"""
    mocker.patch.object(
        neon,
        "search_member",
        return_value=[
            {"Account ID": "1", "Company ID": "2"},
            {"Account ID": "3", "Company ID": "4"},
        ],
    )
    mock_send_membership_automation_message = mocker.patch.object(
        index, "send_membership_automation_message"
    )
    result = index.get_or_activate_member("a@b.com", mocker.MagicMock())
    mock_send_membership_automation_message.assert_called_once()


def test_get_or_activate_deferred(mocker):
    """Test if account automation is deferred"""
    mocker.patch.object(index.comms, "send_email", return_value=None)
    mocker.patch.object(
        neon,
        "search_member",
        return_value=[
            {
                "Account ID": "1",
                "Company ID": "2",
                "individualAccount": {
                    "accountCustomFields": [
                        {"name": "Account Automation Ran", "value": "deferred"}
                    ]
                },
            }
        ],
    )
    mock_set_membership_start_date = mocker.patch.object(
        neon, "set_membership_start_date", return_value=mocker.Mock(status_code=200)
    )
    mock_update_account_automation_run_status = mocker.patch.object(
        neon, "update_account_automation_run_status"
    )

    result = index.get_or_activate_member("a@b.com", lambda msg, pct: None)
    assert result == neon.search_member.return_value[0]
    mock_set_membership_start_date.assert_called_once()
    mock_update_account_automation_run_status.assert_called_once_with("1", "activated")
    index.comms.send_email.assert_called_with(
        MatchStr("active"), Any(), "a@b.com", True
    )


def test_get_or_activate_active_membership(mocker):
    """Test if account is already active"""
    mocker.patch.object(
        neon,
        "search_member",
        return_value=[
            {
                "Account ID": "1",
                "Company ID": "2",
                "Account Current Membership Status": "ACTIVE",
            }
        ],
    )

    result = index.get_or_activate_member("a@b.com", mocker.MagicMock())
    assert result == neon.search_member.return_value[0]


def test_get_or_activate_no_accounts(mocker):
    """Test if no accounts are found"""
    mocker.patch.object(neon, "search_member", return_value=[])
    result = index.get_or_activate_member("a@b.com", mocker.MagicMock())
    assert result is None
