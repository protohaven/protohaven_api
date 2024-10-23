"""Unit tests for sign-in automation flow"""
# pylint: skip-file

import datetime

import pytest
from dateutil import parser as dateparser

from protohaven_api.automation.membership import sign_in as s
from protohaven_api.config import tz, tznow
from protohaven_api.integrations.data.models import SignInEvent
from protohaven_api.testing import Any, MatchStr, d


def test_activate_membership_ok(mocker):
    """Test activate_membership when activation is successful"""
    email = "a@b.com"
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
    """Test sign in form submission"""
    data = {
        "email": "a@b.com",
        "dependent_info": "none",
        "referrer": "friend",
        "person": "member",
    }
    result = {"waiver_signed": True}
    send = mocker.Mock()

    mocker.patch.object(s.forms, "submit_google_form", return_value="google_response")
    mocker.patch.object(s.airtable, "insert_signin", return_value="airtable_response")
    m = mocker.patch.object(s, "_apply_async")

    s.log_sign_in(data, result)
    m.assert_called_once()


def test_get_member_multiple_accounts(mocker):
    email = "a@b.com"
    member_email_cache = {
        email: {
            "1": {"Account ID": "1", "Company ID": "1"},
            "2": {"Account ID": "2", "Company ID": "3"},
            "3": {"Account ID": "3", "Company ID": "4"},
        }
    }
    mocker.patch.object(s, "member_email_cache", member_email_cache)
    mock_notify_async = mocker.patch.object(s, "notify_async")

    result = s.get_member_and_activation_state(email)

    assert result[0] is not None
    mock_notify_async.assert_called_once()


def test_get_member_deferred_account(mocker):
    email = "a@b.com"
    mocker.patch.object(
        s,
        "member_email_cache",
        {
            email: {
                "1": {
                    "Account ID": "1",
                    "Account Automation Ran": "deferred_do_something",
                },
            }
        },
    )

    member, is_deferred = s.get_member_and_activation_state(email)

    assert member is not None
    assert is_deferred


def test_get_member_active_membership(mocker):
    email = "a@b.com"
    mocker.patch.object(
        s,
        "member_email_cache",
        {
            email: {
                "1": {"Account ID": "1", "Account Current Membership Status": "ACTIVE"},
            },
        },
    )

    member, is_deferred = s.get_member_and_activation_state(email)

    assert member is not None
    assert not is_deferred


def test_get_member_no_account_found(mocker):
    email = "a@b.com"
    mocker.patch.object(s, "member_email_cache", {email: {}})

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


def test_handle_announcements_recent_last_ack(mocker):
    """Test announcements handling with a recent last_ack. Also test that survey responses are stripped"""
    mocker.patch.object(
        s.table_cache,
        "announcements_after",
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
        s.table_cache,
        "announcements_after",
        return_value=[
            {"Title": "Testing Announcement"},
        ],
    )
    result = s.handle_announcements(
        "2025-01-01T00:00:00Z", [], ["General"], False, True
    )
    s.table_cache.announcements_after.assert_called_with(Any(), ["Testing"], Any())
    assert result == [{"Title": "Testing Announcement"}]


def test_handle_announcements_is_active(mocker):
    """Test announcements handling for active members"""
    mocker.patch.object(
        s.table_cache,
        "announcements_after",
        return_value=[
            {"Title": "Member Announcement"},
        ],
    )
    result = s.handle_announcements(
        "2025-01-01T00:00:00Z", [], ["General"], True, False
    )
    s.table_cache.announcements_after.assert_called_with(Any(), ["Member"], Any())
    assert result == [{"Title": "Member Announcement"}]


TEST_USER = 1234
NOW = d(0)
NOWSTR = NOW.strftime("%Y-%m-%d")
OLDSTR = (NOW - datetime.timedelta(days=90)).strftime("%Y-%m-%d")


@pytest.mark.parametrize(
    "ack,called",
    [
        (False, False),
        (True, True),
    ],
)
def test_handle_waiver_no_data(mocker, ack, called):
    """When given no existing waiver data for the user, only return
    true if the user has just acknowledged the waiver"""
    m = mocker.patch.object(s, "_apply_async")
    mocker.patch.object(s, "get_config", side_effect=["2024-01-01", 30])
    assert s.handle_waiver(TEST_USER, None, ack) is ack
    if called:
        m.assert_called()
    else:
        m.assert_not_called()


@pytest.mark.parametrize(
    "ver,ack_date,ack,ok,called",
    [
        (OLDSTR, NOWSTR, False, False, False),
        (NOWSTR, NOWSTR, False, True, False),
        (OLDSTR, NOWSTR, True, True, True),
    ],
)
def test_handle_waiver_checks_version(mocker, ver, ack_date, ack, ok, called):
    """handle_waiver returns false if the most recent signed
    version of the waiver is not the current version hosted by the server"""
    m = mocker.patch.object(s, "_apply_async")
    assert (
        s.handle_waiver(
            TEST_USER,
            f"version {ver} on {ack_date}",
            ack,
            current_version=NOWSTR,
            expiration_days=30,
            now=NOW,
        )
        is ok
    )
    if called:
        m.assert_called()
    else:
        m.assert_not_called()


def test_handle_waiver_checks_expiration(mocker):
    """handle_waiver returns false if the most recent signed
    waiver data of the user is older than `expiration_days`"""
    m = mocker.patch.object(s, "_apply_async")
    args = [TEST_USER, f"version {OLDSTR} on {OLDSTR}", False]
    kwargs = {"now": NOW, "current_version": OLDSTR}

    assert s.handle_waiver(*args, **kwargs, expiration_days=1000) is True
    assert s.handle_waiver(*args, **kwargs, expiration_days=30) is False
    m.assert_not_called()  # No mutation

    # Acknowledgement triggers update
    args[-1] = True
    assert s.handle_waiver(*args, **kwargs, expiration_days=30) is True
    m.assert_called_with(
        s.neon.set_waiver_status, (1234, "version 2024-10-03 on 2025-01-01")
    )


def test_as_guest_no_referrer(mocker):
    """Guest data with no referrer is omitted from form submission"""
    m = mocker.patch.object(s, "_apply_async")
    got = s.as_guest({"person": "guest", "waiver_ack": True})
    assert got["waiver_signed"] == True
    m.assert_not_called()


def test_as_guest_referrer(mocker):
    """Guest sign in with referrer data is submitted"""
    m = mocker.patch.object(s, "_apply_async")
    s.as_guest(
        {
            "person": "guest",
            "waiver_ack": True,
            "referrer": "TEST",
            "email": "a@b.com",
            "dependent_info": "DEP_INFO",
        }
    )
    m.assert_called()


def test_as_member_notfound(mocker):
    """Ensure form does not get called if member not found"""
    m = mocker.patch.object(s, "_apply_async")
    s.neon.search_member.return_value = []
    got = s.as_member(
        {
            "person": "member",
            "waiver_ack": True,
            "referrer": "TEST",
            "email": "a@b.com",
            "dependent_info": "DEP_INFO",
        },
        mocker.MagicMock(),
    )
    assert got == {
        "announcements": [],
        "firstname": "member",
        "notfound": True,
        "status": False,
        "violations": [],
        "waiver_signed": False,
    }
    m.assert_not_called()


def test_as_member_expired(mocker):
    """Ensure form submits and proper status returns on expired membership"""
    m = mocker.patch.object(s, "_apply_async")
    l = mocker.patch.object(s, "log_sign_in")
    mocker.patch.object(s, "notify_async")
    mocker.patch.object(
        s,
        "member_email_cache",
        {
            "a@b.com": {
                12345: {
                    "Account ID": 12345,
                    "Account Current Membership Status": "Inactive",
                    "First Name": "First",
                    "API server role": None,  # This can happen
                }
            },
        },
    )
    mocker.patch.object(s.table_cache, "announcements_after", return_value=[])
    mocker.patch.object(s.table_cache, "violations_for", return_value=[])
    mocker.patch.object(s, "tznow", return_value=d(0))
    rep = s.as_member(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "a@b.com",
            "dependent_info": "DEP_INFO",
        },
        mocker.MagicMock(),
    )
    assert rep["status"] == "Inactive"
    l.assert_called()
    m.assert_called_with(
        s.neon.set_waiver_status, (12345, "version 2023-03-14 on 2025-01-01")
    )
    s.notify_async.assert_called_with(
        "[First (a@b.com)](https://protohaven.app.neoncrm.com/admin/accounts/12345) just signed in at the front desk but has a non-Active membership status in Neon: status is Inactive ([wiki](https://protohaven.org/wiki/software/membership_validation))\n"
    )


def test_as_member_violations(mocker):
    """Test that form submission triggers and announcements are returned when OK member logs in"""
    m = mocker.patch.object(s, "_apply_async")
    mocker.patch.object(s, "notify_async")
    mocker.patch.object(
        s,
        "member_email_cache",
        {
            "a@b.com": {
                12345: {
                    "Account ID": 12345,
                    "Account Current Membership Status": "Active",
                    "First Name": "First",
                }
            }
        },
    )
    mocker.patch.object(s.table_cache, "announcements_after", return_value=[])
    mocker.patch.object(
        s.table_cache,
        "violations_for",
        return_value=[
            {"fields": {"Neon ID": "12345", "Notes": "This one is shown"}},
        ],
    )
    rep = s.as_member(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "a@b.com",
            "dependent_info": "DEP_INFO",
        },
        mocker.MagicMock(),
    )
    assert rep["violations"] == [
        {"fields": {"Neon ID": "12345", "Notes": "This one is shown"}}
    ]
    s.notify_async.assert_called_with(
        "[First (a@b.com)](https://protohaven.app.neoncrm.com/admin/accounts/12345) just signed in at the front desk with violations: `[{'fields': {'Neon ID': '12345', 'Notes': 'This one is shown'}}]` ([wiki](https://protohaven.org/wiki/software/membership_validation))\n"
    )


def test_as_member_duplicates(mocker):
    """Test that form submission triggers and a discord notification is sent if there's duplicate accounts"""
    m = mocker.patch.object(s, "_apply_async")
    mocker.patch.object(s, "notify_async")
    mocker.patch.object(
        s,
        "member_email_cache",
        {
            "a@b.com": {
                12346: {
                    "Account ID": 12346,  # Extra membership, makes things ambiguous
                },
                12345: {
                    "Account ID": 12345,
                    "Account Current Membership Status": "Active",
                    "First Name": "First",
                    "API server role": "Shop Tech",
                },
            }
        },
    )
    mocker.patch.object(s.table_cache, "announcements_after", return_value=[])
    mocker.patch.object(s.table_cache, "violations_for", return_value=[])
    rep = s.as_member(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "a@b.com",
            "dependent_info": "DEP_INFO",
        },
        mocker.MagicMock(),
    )
    assert rep["status"] == "Active"
    s.notify_async.mock_calls[0].args[0].startswith(
        "Sign-in with a@b.com returned multiple accounts in Neon with same email"
    )


def test_as_member_announcements(mocker):
    """Test that form submission triggers and announcements are returned when OK member logs in"""
    m = mocker.patch.object(s, "_apply_async")
    mocker.patch.object(s, "notify_async")
    mocker.patch.object(s, "tznow", return_value=d(0))
    mocker.patch.object(
        s,
        "member_email_cache",
        {
            "a@b.com": {
                12346: {
                    "Account ID": 12345,
                    "Account Current Membership Status": "Active",
                    "First Name": "First",
                    "API server role": "Shop Tech",
                }
            }
        },
    )
    mocker.patch.object(
        s.table_cache,
        "announcements_after",
        return_value=[
            {
                "Published": d(0).isoformat(),
                "Roles": ["Shop Tech"],
                "Title": "test Announcement",
            },
        ],
    )
    mocker.patch.object(s.table_cache, "violations_for", return_value=[])
    rep = s.as_member(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "a@b.com",
            "dependent_info": "DEP_INFO",
        },
        mocker.MagicMock(),
    )
    assert rep["status"] == "Active"
    assert rep["announcements"] == [
        {
            "Published": d(0).isoformat(),
            "Roles": ["Shop Tech"],
            "Title": "test Announcement",
        }
    ]
    m.assert_called_with(
        s.submit_forms,
        args=(
            SignInEvent(
                email="a@b.com",
                dependent_info="DEP_INFO",
                waiver_ack=True,
                referrer=None,
                purpose="I'm a member, just signing in!",
                am_member=True,
            ),
        ),
    )


def test_as_member_company_id(mocker):
    """Test that form submission triggers and a discord notification is sent if there's duplicate accounts"""
    mocker.patch.object(s, "_apply_async")
    mocker.patch.object(s, "notify_async")
    mocker.patch.object(
        s,
        "member_email_cache",
        {
            "a@b.com": {
                12346: {
                    "Account ID": 12346,
                    "Company ID": 12346,  # Matches account ID, so ignored
                },
                12345: {
                    "Account ID": 12345,
                    "Company ID": 12346,
                    "Account Current Membership Status": "Active",
                    "First Name": "First",
                    "API server role": "Shop Tech",
                },
            }
        },
    )
    mocker.patch.object(s.table_cache, "announcements_after", return_value=[])
    mocker.patch.object(s.table_cache, "violations_for", return_value=[])
    rep = s.as_member(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "a@b.com",
            "dependent_info": "DEP_INFO",
        },
        mocker.MagicMock(),
    )
    assert rep["status"] == "Active"
    s.notify_async.assert_not_called()


def test_as_member_notify_board_and_staff(mocker):
    """Test that a discord notification is sent if the account is flagged"""
    mocker.patch.object(s, "_apply_async")
    mocker.patch.object(s, "notify_async")
    mocker.patch.object(
        s,
        "member_email_cache",
        {
            "a@b.com": {
                12345: {
                    "Account ID": 12345,
                    "Account Current Membership Status": "Active",
                    "First Name": "First",
                    "Notify Board & Staff": "On Sign In|Other Unrelated Condition",
                },
            }
        },
    )
    mocker.patch.object(s.table_cache, "announcements_after", return_value=[])
    mocker.patch.object(s.table_cache, "violations_for", return_value=[])
    rep = s.as_member(
        {
            "person": "member",
            "waiver_ack": True,
            "email": "a@b.com",
            "dependent_info": "DEP_INFO",
        },
        mocker.MagicMock(),
    )
    s.notify_async.assert_called_with(
        "@Board and @Staff: [First (a@b.com)](https://protohaven.app.neoncrm.com/admin/accounts/12345) just signed in at the front desk with `Notify Board & Staff = On Sign In`. This indicator suggests immediate followup with this member is needed. Click the name/email link for notes in Neon CRM."
    )


def test_activate_membership(mocker):
    mocker.patch.object(s, "notify_async", return_value=None)
    m1 = mocker.patch.object(
        s.neon, "set_membership_start_date", return_value=mocker.Mock(status_code=200)
    )
    m2 = mocker.patch.object(s.neon, "update_account_automation_run_status")
    m3 = mocker.patch.object(s.comms, "send_email")
    s.activate_membership("123", "fname", "a@b.com")
    m1.assert_called_once()
    m2.assert_called_once_with("123", "activated")
    m3.assert_called_once_with(MatchStr("active"), Any(), "a@b.com", Any())


def test_activate_membership_failure(mocker):
    m0 = mocker.patch.object(s, "notify_async", return_value=None)
    mocker.patch.object(
        s.neon,
        "set_membership_start_date",
        return_value=mocker.Mock(status_code=123, content="test"),
    )
    m2 = mocker.patch.object(s.neon, "update_account_automation_run_status")
    m3 = mocker.patch.object(s.comms, "send_email")
    s.activate_membership("123", "fname", "a@b.com")

    m0.assert_called_with(MatchStr("Error 123 activating membership for #123"))
    m2.assert_not_called()
    m3.assert_not_called()
