"""Verify proper behavior of instructor pages"""
# pylint: skip-file
import datetime
import json

import pytest
from dateutil import parser as dateparser

from protohaven_api import rbac
from protohaven_api.config import tz
from protohaven_api.handlers import instructor
from protohaven_api.main import app


@pytest.fixture()
def client():
    rbac.set_rbac(False)
    return app.test_client()


def test_class_no_clearances():
    """Ensure that a class without clearances still loads the page."""
    pytest.skip("todo")


TEST_EMAIL = "test@email.com"
now = datetime.datetime.now()


def dt(days=0, hours=0):
    """Return a datetime that's `days` and `hours` offset from now"""
    return now + datetime.timedelta(days=days, hours=hours)


def _sched(_id, email=TEST_EMAIL, start=now, days=1, confirmed=None):
    """Create and return a fake Airtable schedule record"""
    return {
        "id": _id,
        "fields": {
            "Email": email,
            "Start Time": start.isoformat(),
            "Confirmed": None if not confirmed else confirmed.isoformat(),
            "Days (from Class)": [days],
        },
    }


def test_dashboard_schedule(mocker):
    """Confirm behavior of shown and hidden schedule items for the instructor dashboard"""
    mocker.patch(
        "protohaven_api.integrations.airtable.get_class_automation_schedule",
        return_value=[
            _sched(
                "Unconfirmed, too close HIDDEN",
                confirmed=None,
                start=dt(instructor.HIDE_UNCONFIRMED_DAYS_AHEAD - 1),
            ),
            _sched(
                "Unconfirmed, not too close",
                confirmed=None,
                start=dt(instructor.HIDE_UNCONFIRMED_DAYS_AHEAD + 1),
            ),
            _sched(
                "Confirmed, too old HIDDEN",
                confirmed=now,
                start=dt(-instructor.HIDE_CONFIRMED_DAYS_AFTER - 1),
            ),
            _sched(
                "Confirmed, after run, not too old",
                confirmed=now,
                start=dt(-instructor.HIDE_CONFIRMED_DAYS_AFTER + 1),
            ),
            _sched("Bad email", confirmed=now, start=now, email="bad@bad.com"),
        ],
    )
    got = {g[0] for g in instructor.get_dashboard_schedule_sorted(TEST_EMAIL)}
    assert got == {"Unconfirmed, not too close", "Confirmed, after run, not too old"}


def test_prefill(mocker):
    mocker.patch.object(
        instructor.airtable, "get_instructor_log_tool_codes", return_value=[]
    )
    assert instructor.prefill_form(
        instructor="test_instructor",
        start_date=datetime.datetime.now(),
        hours=3,
        class_name="test class",
        pass_emails="a@b.com, c@d.com",
        clearances=["3DF"],
        volunteer=False,
        event_id=12345,
    )


def test_instructor_class_attendees(client, mocker):
    mocker.patch.object(
        instructor.neon, "fetch_attendees", return_value=[{"accountId": 123}]
    )
    mocker.patch.object(
        instructor.neon,
        "fetch_account",
        return_value={"individualAccount": {"primaryContact": {"email1": "a@b.com"}}},
    )
    result = client.get("/instructor/class/attendees?id=12345")
    rep = json.loads(result.data.decode("utf8"))
    assert rep == [{"accountId": 123, "email": "a@b.com"}]


def test_get_dashboard_schedule_sorted(mocker):
    mocker.patch.object(
        instructor.airtable,
        "get_class_automation_schedule",
        return_value=[
            {"fields": {"Email": "nomatch"}},
            {"fields": {"Email": "match", "Rejected": "2024-01-01"}},
            {
                "id": "asdf",
                "fields": {
                    "Email": "match",
                    "Start Time": "2024-01-01",
                    "Days (from Class)": [1],
                    "Confirmed": "2024-01-01",
                },
            },
        ],
    )
    sched = instructor.get_dashboard_schedule_sorted(
        "match", now=dateparser.parse("2024-01-01").astimezone(tz)
    )
    assert len(sched) == 1
    assert sched[0][0] == "asdf"


def test_instructor_about_from_session(client, mocker):
    with client.session_transaction() as session:
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
    mocker.patch.object(instructor.neon, "search_member")
    mocker.patch.object(instructor, "get_instructor_readiness")
    client.get("/instructor/about")
    instructor.neon.search_member.assert_called_with("foo@bar.com")


def test_instructor_about_both_email_and_session(mocker, client):
    """Being logged in as an instructor should not preclude them from using
    the url param if it's their own email"""
    rbac.set_rbac(True)
    mocker.patch.object(rbac, "get_roles", return_value=[rbac.Role.INSTRUCTOR["name"]])

    with client.session_transaction() as session:
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
    mocker.patch.object(instructor.neon, "search_member", return_value=["test"])
    mocker.patch.object(instructor, "get_instructor_readiness")

    rep = client.get("/instructor/about?email=a@b.com")
    assert rep.status == "401 UNAUTHORIZED"

    rep = client.get("/instructor/about?email=foo@bar.com")
    assert rep.status == "200 OK"


def test_class_details_both_email_and_session(mocker, client):
    """Being logged in as an instructor should not preclude them from using
    the url param if it's their own email"""
    rbac.set_rbac(True)
    mocker.patch.object(rbac, "get_roles", return_value=[rbac.Role.INSTRUCTOR["name"]])

    with client.session_transaction() as session:
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
    mocker.patch.object(instructor, "get_dashboard_schedule_sorted")
    mocker.patch.object(instructor.airtable, "get_instructor_email_map")

    rep = client.get("/instructor/class_details?email=a@b.com")
    assert rep.status == "401 UNAUTHORIZED"

    rep = client.get("/instructor/class_details?email=foo@bar.com")
    assert rep.status == "200 OK"


def test_get_instructor_readiness_all_bad(mocker):
    mocker.patch.object(instructor, "airtable")
    instructor.airtable.fetch_instructor_capabilities.return_value = None
    result = instructor.get_instructor_readiness(
        [
            {
                "Account ID": 12345,
                "Account Current Membership Status": "Inactive",
                "First Name": "First",
                "Last Name": "Last",
            },
            {
                "Account ID": 12346,
                "First Name": "Duplicate",
                "Last Name": "Person",
            },
        ]
    )
    assert result == {
        "airtable_id": None,
        "neon_id": 12345,
        "fullname": "First Last",
        "active_membership": "Inactive",
        "discord_user": "missing",
        "email": "2 duplicate accounts in Neon",
        "capabilities_listed": "missing",
        "paperwork": "unknown",
        "profile_img": None,
        "bio": None,
    }


def test_get_instructor_readiness_all_ok(mocker):
    mocker.patch.object(instructor, "airtable")
    instructor.airtable.fetch_instructor_capabilities.return_value = {
        "id": "inst_id",
        "fields": {
            "Class": [1, 2, 3],
            "W9 Form": "<file>",
            "Direct Deposit Info": "<file>",
            "Profile Pic": [{"url": "<url>"}],
            "Bio": "test bio",
        },
    }
    result = instructor.get_instructor_readiness(
        [
            {
                "Account ID": 12345,
                "Account Current Membership Status": "Active",
                "Discord User": "discord_user",
                "First Name": "First     ", # Egregious space in the name doesn't cause lookup error
                "Last Name": "Last",
            }
        ]
    )
    assert result == {
        "airtable_id": "inst_id",
        "neon_id": 12345,
        "fullname": "First Last",
        "active_membership": "OK",
        "discord_user": "OK",
        "email": "OK",
        "capabilities_listed": "OK",
        "paperwork": "OK",
        "profile_img": "<url>",
        "bio": "test bio",
    }
