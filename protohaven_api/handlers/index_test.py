"""Verify proper behavior of public access pages"""
# pylint: skip-file
import json

import pytest

from protohaven_api.handlers import index
from protohaven_api.main import app
from protohaven_api.rbac import set_rbac


@pytest.fixture()
def client():
    set_rbac(False)
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


def test_welcome_signin_get(client):
    """Check that the svelte page is loaded"""
    assert "Welcome! Please sign in" in client.get("/welcome").data.decode("utf8")


def test_welcome_signin_guest_no_referrer(client, mocker):
    """Guest data with no referrer is omitted from form submission"""
    mocker.patch.object(index, "submit_google_form")
    response = client.post("/welcome", json={"person": "guest", "waiver_ack": True})
    rep = json.loads(response.data.decode("utf8"))
    assert rep["waiver_signed"] == True
    index.submit_google_form.assert_not_called()


def test_welcome_signin_guest_referrer(client, mocker):
    """Guest sign in with referrer data is submitted"""
    mocker.patch.object(index, "submit_google_form")
    response = client.post(
        "/welcome",
        json={
            "person": "guest",
            "waiver_ack": True,
            "referrer": "TEST",
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    json.loads(response.data.decode("utf8"))
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


def test_welcome_signin_notfound(client, mocker):
    """Ensure form does not get called if member not found"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index, "neon")
    index.neon.search_member.return_value = []
    response = client.post(
        "/welcome",
        json={
            "person": "member",
            "waiver_ack": True,
            "referrer": "TEST",
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    assert json.loads(response.data.decode("utf8")) == {
        "announcements": [],
        "firstname": "member",
        "notfound": True,
        "status": False,
        "violations": [],
        "waiver_signed": False,
    }
    index.submit_google_form.assert_not_called()


def test_welcome_signin_membership_expired(client, mocker):
    """Ensure form submits and proper status returns on expired membership"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index, "neon")
    mocker.patch.object(index, "airtable")
    index.neon.search_member.return_value = [
        {
            "Account ID": 12345,
            "Account Current Membership Status": "Inactive",
            "First Name": "First",
            "API server role": None,  # This can happen
        }
    ]
    index.airtable.get_announcements_after.return_value = None
    index.neon.update_waiver_status.return_value = True
    response = client.post(
        "/welcome",
        json={
            "person": "member",
            "waiver_ack": True,
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    assert json.loads(response.data.decode("utf8"))["status"] == "Inactive"
    index.submit_google_form.assert_called()  # Form submission even if membership is expired


def test_welcome_signin_ok_with_violations(client, mocker):
    """Test that form submission triggers and announcements are returned when OK member logs in"""
    mocker.patch.object(index, "submit_google_form")
    mocker.patch.object(index, "neon")
    mocker.patch.object(index, "airtable")
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
    response = client.post(
        "/welcome",
        json={
            "person": "member",
            "waiver_ack": True,
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    rep = json.loads(response.data.decode("utf8"))
    assert rep["violations"] == [
        {"fields": {"Neon ID": "12345", "Notes": "This one is shown"}}
    ]


def test_welcome_signin_ok_with_announcements(client, mocker):
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
    response = client.post(
        "/welcome",
        json={
            "person": "member",
            "waiver_ack": True,
            "email": "foo@bar.com",
            "dependent_info": "DEP_INFO",
        },
    )
    rep = json.loads(response.data.decode("utf8"))
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
