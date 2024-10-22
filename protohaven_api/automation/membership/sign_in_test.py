"""Unit tests for sign-in automation flow"""
# pylint: skip-file

import datetime

import pytest

from protohaven_api.automation.membership import sign_in as s
from protohaven_api.config import tznow
from protohaven_api.testing import Any, MatchStr


def test_activate_membership_ok(mocker):
    """Test activate_membership when activation is successful"""
    email = "test@example.com"
    mock_response = mocker.Mock()
    mock_response.status_code = 200

    mocker.patch.object(s.neon, "set_membership_start_date", return_value=mock_response)
    mocker.patch.object(s.neon, "update_account_automation_run_status")
    mocker.patch.object(
        s.comms.Msg,
        "tmpl",
        return_value=mocker.MagicMock(subject="Subject", body="Body", html=True),
    )
    mocker.patch.object(s.comms, "send_email")

    s.activate_membership("12345", "John", email)

    s.neon.set_membership_start_date.assert_called_once_with("12345", mocker.ANY)
    s.neon.update_account_automation_run_status.assert_called_once_with(
        "12345", "activated"
    )
    s.comms.Msg.tmpl.assert_called_once_with(
        "membership_activated", fname="John", target=email
    )
    s.comms.send_email.assert_called_once_with("Subject", "Body", email, True)


def test_activate_membership_fail(mocker):
    """Test activate_membership when activation fails"""
    mock_response = mocker.Mock(status_code=500, content="Internal Server Error")
    mocker.patch.object(s.neon, "set_membership_start_date", return_value=mock_response)
    mocker.patch.object(s.neon, "update_account_automation_run_status")
    mocker.patch.object(s.comms, "send_email")
    mocker.patch.object(s, "notify_async")

    s.activate_membership("12345", "John", "a@b.com")

    s.notify_async.assert_called_once_with(MatchStr("Error 500"))
    s.comms.send_email.assert_not_called()
    s.neon.update_account_automation_run_status.assert_not_called()


def test_log_sign_in(mocker):
    """Test that submit_google_form and insert_signin are both called"""
    data = {
        "email": "test@example.com",
        "dependent_info": "none",
        "referrer": "friend",
        "person": "member",
    }
    result = {"waiver_signed": True}
    send = mocker.Mock()

    mocker.patch.object(s.forms, "submit_google_form", return_value="google_response")
    mocker.patch.object(s.airtable, "insert_signin", return_value="airtable_response")

    s.log_sign_in(data, result, send)

    s.forms.submit_google_form.assert_called_once_with("signin", mocker.ANY)
    s.airtable.insert_signin.assert_called_once_with(mocker.ANY)


def test_get_member_multiple_accounts(mocker):
    email = "test@example.com"
    member_email_cache = {
        email: [
            {"Account ID": "1", "Company ID": "1"},
            {"Account ID": "2", "Company ID": "3"},
            {"Account ID": "3", "Company ID": "4"},
        ]
    }
    mocker.patch.object(s, "member_email_cache", member_email_cache)
    mock_notify_async = mocker.patch.object(s, "notify_async")

    result = s.get_member_and_activation_state(email)

    assert result[0] is not None
    mock_notify_async.assert_called_once()


def test_get_member_deferred_account(mocker):
    email = "test@example.com"
    mocker.patch.object(
        s,
        "member_email_cache",
        {
            email: [
                {
                    "Account ID": "1",
                    "individualAccount": {
                        "accountCustomFields": [
                            {
                                "name": "Account Automation Ran",
                                "value": "deferred_do_something",
                            }
                        ]
                    },
                },
            ]
        },
    )

    member, is_deferred = s.get_member_and_activation_state(email)

    assert member is not None
    assert is_deferred


def test_get_member_active_membership(mocker):
    email = "test@example.com"
    mocker.patch.object(
        s,
        "member_email_cache",
        {
            email: [
                {"Account ID": "1", "Account Current Membership Status": "ACTIVE"},
            ]
        },
    )

    member, is_deferred = s.get_member_and_activation_state(email)

    assert member is not None
    assert not is_deferred


def test_get_member_no_account_found(mocker):
    email = "test@example.com"
    mocker.patch.object(s, "member_email_cache", {email: []})

    member, is_deferred = s.get_member_and_activation_state(email)

    assert member is None
    assert not is_deferred


def test_handle_notify_board_and_staff(mocker):
    """Test notification when 'On Sign In' is in notify_str"""
    mock_notify_async = mocker.patch.object(s, "notify_async")

    s.handle_notify_board_and_staff(
        "On Sign In", "John", "john@example.com", "http://example.com"
    )
    mock_notify_async.assert_called_once_with(MatchStr("immediate followup"))


def test_handle_notify_inactive(mocker):
    """Test notification when member status is not active"""
    mock_notify_async = mocker.patch.object(s, "notify_async")

    s.handle_notify_inactive(
        "Inactive", "Jane", "jane@example.com", "http://example.com"
    )
    mock_notify_async.assert_called_once_with(MatchStr("non-Active membership"))


def test_handle_notify_violations(mocker):
    """Test notification when there are violations"""
    mock_notify_async = mocker.patch.object(s, "notify_async")

    s.handle_notify_violations(
        ["Overdue fees"], "Dana", "dana@example.com", "http://example.com"
    )
    mock_notify_async.assert_called_once_with(MatchStr("Overdue fees"))


def test_get_storage_violations(mocker):
    """Test checking member for storage violations"""
    account_id = "123"
    mock_violations = [
        {"fields": {"Neon ID": account_id, "Violation": "Excessive storage"}},
        {"fields": {"Neon ID": "456", "Closure": "2023-10-01"}},
        {"fields": {"Neon ID": account_id, "Closure": "2023-10-01"}},
    ]
    mocker.patch.object(
        s.airtable, "get_policy_violations", return_value=mock_violations
    )

    violations = list(s.get_storage_violations(account_id))

    assert len(violations) == 1
    assert violations[0]["fields"]["Violation"] == "Excessive storage"
    assert "Closure" not in violations[0]["fields"]


def test_handle_announcements_recent_last_ack(mocker):
    """Test announcements handling with a recent last_ack. Also test that survey responses are stripped"""
    mocker.patch.object(
        s.airtable,
        "get_announcements_after",
        return_value=[
            {"name": "a", "Sign-In Survey Responses": [1, 2, 3]},
        ],
    )
    assert s.handle_announcements(
        "2025-02-01T00:00:00Z", [], ["General"], False, False
    ) == [
        {"name": "a"},
    ]


def test_handle_announcements_testing(mocker):
    """Test announcements handling with testing enabled"""
    mocker.patch.object(
        s.airtable,
        "get_announcements_after",
        return_value=[
            {"Title": "Testing Announcement"},
        ],
    )
    result = s.handle_announcements(
        "2025-01-01T00:00:00Z", [], ["General"], False, True
    )
    s.airtable.get_announcements_after.assert_called_with(Any(), ["Testing"], Any())
    assert result == [{"Title": "Testing Announcement"}]


def test_handle_announcements_is_active(mocker):
    """Test announcements handling for active members"""
    mocker.patch.object(
        s.airtable,
        "get_announcements_after",
        return_value=[
            {"Title": "Member Announcement"},
        ],
    )
    result = s.handle_announcements(
        "2025-01-01T00:00:00Z", [], ["General"], True, False
    )
    s.airtable.get_announcements_after.assert_called_with(Any(), ["Member"], Any())
    assert result == [{"Title": "Member Announcement"}]


TEST_USER = 1234
NOW = tznow()
NOWSTR = NOW.strftime("%Y-%m-%d")
OLDSTR = (NOW - datetime.timedelta(days=90)).strftime("%Y-%m-%d")


def test_update_waiver_status_no_data(mocker):
    """When given no existing waiver data for the user, only return
    true if the user has just acknowledged the waiver"""
    m = mocker.patch.object(neon, "set_waiver_status")
    mocker.patch.object(neon, "cfg")
    assert neon.update_waiver_status(TEST_USER, None, False) is False
    m.assert_not_called()  # No mutation

    # Acknowledgement triggers update
    assert neon.update_waiver_status(TEST_USER, None, True) is True
    m.assert_called()


def test_update_waiver_status_checks_version(mocker):
    """update_waiver_status returns false if the most recent signed
    version of the waiver is not the current version hosted by the server"""
    m = mocker.patch.object(neon, "set_waiver_status")
    mocker.patch.object(neon, "cfg", return_value=3)
    args = [TEST_USER, False]
    kwargs = {"now": NOW, "current_version": NOWSTR}
    assert (
        neon.update_waiver_status(
            args[0], f"version {OLDSTR} on {NOWSTR}", args[1], **kwargs
        )
        is False
    )
    assert (
        neon.update_waiver_status(
            args[0], f"version {NOWSTR} on {NOWSTR}", args[1], **kwargs
        )
        is True
    )
    m.assert_not_called()  # No mutation

    # Acknowledgement triggers update
    assert (
        neon.update_waiver_status(
            args[0], f"version {OLDSTR} on {NOWSTR}", True, **kwargs
        )
        is True
    )
    m.assert_called()


def test_update_waiver_status_checks_expiration(mocker):
    """update_waiver_status returns false if the most recent signed
    waiver data of the user is older than `expiration_days`"""
    m = mocker.patch.object(neon, "set_waiver_status")
    args = [TEST_USER, f"version {OLDSTR} on {OLDSTR}", False]
    kwargs = {"now": NOW, "current_version": OLDSTR}

    assert neon.update_waiver_status(*args, **kwargs, expiration_days=1000) is True
    assert neon.update_waiver_status(*args, **kwargs, expiration_days=30) is False
    m.assert_not_called()  # No mutation

    # Acknowledgement triggers update
    args[-1] = True
    assert neon.update_waiver_status(*args, **kwargs, expiration_days=30) is True
    m.assert_called()


@pytest.mark.parametrize(
    "desc, data, want",
    [
        (
            "correct role & tool code",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": ["Sandblaster"],
            },
            True,
        ),
        (
            "correct role, non cleared tool code",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": ["Planer"],
            },
            False,
        ),
        (
            "wrong role, cleared tool",
            {
                "Published": "2024-04-01",
                "Roles": ["badrole"],
                "Tool Name (from Tool Codes)": ["Sandblaster"],
            },
            False,
        ),
        (
            "Correct role, no tool",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            True,
        ),
        (
            "too old",
            {
                "Published": "2024-03-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            False,
        ),
        (
            "too new (scheduled)",
            {
                "Published": "2024-05-05",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            False,
        ),
    ],
)
def test_get_announcements_after(desc, data, want, mocker):
    mocker.patch.object(
        a,
        "_get_announcements_cached_impl",
        return_value=[{"fields": data, "id": "123"}],
    )
    mocker.patch.object(
        a, "tznow", return_value=dateparser.parse("2024-04-02").astimezone(tz)
    )
    got = list(
        a.get_announcements_after(
            dateparser.parse("2024-03-14").astimezone(tz), ["role1"], ["Sandblaster"]
        )
    )
    if want:
        assert got
    else:
        assert not got
