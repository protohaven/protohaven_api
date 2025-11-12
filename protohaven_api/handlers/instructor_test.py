"""Verify proper behavior of instructor pages"""

# pylint: skip-file
import datetime
import json

import pytest

from protohaven_api import rbac
from protohaven_api.config import safe_parse_datetime, tz
from protohaven_api.handlers import instructor
from protohaven_api.testing import d, fixture_client


@pytest.fixture(name="inst_client")
def fixture_inst_client(client):
    with client.session_transaction() as session:
        session["neon_account"] = {
            "individualAccount": {
                "accountCustomFields": [
                    {
                        "name": "API server role",
                        "optionValues": [{"name": "Instructor"}],
                    },
                ],
                "primaryContact": {
                    "firstName": "First",
                    "lastName": "Last",
                    "email1": "foo@bar.com",
                },
            }
        }
    return client


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
            "Recurrence (from Class)": (
                [f"RRULE:FREQ=WEEKLY;COUNT={days}"] if days > 1 else None
            ),
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


def test_instructor_class_attendees(inst_client, mocker):
    mocker.patch.object(
        instructor.neon, "fetch_attendees", return_value=[{"accountId": 123}]
    )
    mocker.patch.object(
        instructor.neon.neon_base,
        "fetch_account",
        return_value=mocker.MagicMock(email="a@b.com"),
    )
    result = inst_client.get("/instructor/class/attendees?id=12345")
    assert result.status_code == 200
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
                    "Confirmed": "2024-01-01",
                },
            },
        ],
    )
    sched = instructor.get_dashboard_schedule_sorted(
        "match", now=safe_parse_datetime("2024-01-01")
    )
    assert len(sched) == 1
    assert sched[0][0] == "asdf"


def test_instructor_about_from_session(inst_client, mocker):
    mocker.patch.object(instructor.neon, "search_members_by_email", return_value=[{}])
    mocker.patch.object(instructor, "get_instructor_readiness")
    rep = inst_client.get("/instructor/about")
    assert rep.status_code == 200
    instructor.neon.search_members_by_email.assert_called_with("foo@bar.com")


def test_instructor_about_both_email_and_session(mocker, inst_client):
    """Being logged in as an instructor should not preclude them from using
    the url param if it's their own email"""
    rbac.set_rbac(True)
    mocker.patch.object(rbac, "get_roles", return_value=[rbac.Role.INSTRUCTOR["name"]])
    mocker.patch.object(
        instructor.neon, "search_members_by_email", return_value=["test"]
    )
    mocker.patch.object(instructor, "get_instructor_readiness")

    rep = inst_client.get("/instructor/about?email=a@b.com")
    assert rep.status == "401 UNAUTHORIZED"

    rep = inst_client.get("/instructor/about?email=foo@bar.com")
    assert rep.status == "200 OK"


def test_class_details_both_email_and_session(mocker, inst_client):
    """Being logged in as an instructor should not preclude them from using
    the url param if it's their own email"""
    rbac.set_rbac(True)
    mocker.patch.object(rbac, "get_roles", return_value=[rbac.Role.INSTRUCTOR["name"]])
    mocker.patch.object(instructor, "get_dashboard_schedule_sorted")
    mocker.patch.object(instructor.airtable, "get_instructor_email_map")

    rep = inst_client.get("/instructor/class_details?email=a@b.com")
    assert rep.status == "401 UNAUTHORIZED"

    rep = inst_client.get("/instructor/class_details?email=foo@bar.com")
    assert rep.status == "200 OK"


def test_get_instructor_readiness_all_bad(mocker):
    mocker.patch.object(instructor, "airtable")
    instructor.airtable.fetch_instructor_capabilities.return_value = None
    result = instructor.get_instructor_readiness(
        [
            mocker.MagicMock(
                neon_id=12345,
                account_current_membership_status="Inactive",
                fname="First",
                lname="Last",
                discord_user=None,
            ),
            mocker.MagicMock(
                neon_id=12346,
                fname="Duplicate",
                lname="Person",
                discord_user=None,
            ),
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
            mocker.MagicMock(
                neon_id=12345,
                account_current_membership_status="Active",
                fname="First",
                lname="Last",
                discord_user="discord_user",
            ),
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


def test_instructor_class_supply_req(mocker, inst_client):
    """Test marking supplies as missing or confirmed for a class"""
    mocker.patch.object(
        instructor.airtable,
        "get_scheduled_class",
        return_value={
            "fields": {
                "Name (from Class)": ["Class Name"],
                "Instructor": "Instructor Name",
                "Start Time": d(0).isoformat(),
            }
        },
    )
    mocker.patch.object(
        instructor.airtable,
        "mark_schedule_supply_request",
        return_value=(
            200,
            {"fields": {"id": "rec123", "Start Time": d(0).isoformat()}},
        ),
    )
    mocker.patch.object(instructor.comms, "send_discord_message")

    response = inst_client.post(
        "/instructor/class/supply_req", json={"eid": "class123", "missing": True}
    )

    assert response.status_code == 200
    instructor.airtable.get_scheduled_class.assert_called_once_with("class123")
    instructor.airtable.mark_schedule_supply_request.assert_called_once_with(
        "class123", "Supplies Requested"
    )
    instructor.comms.send_discord_message.assert_called_once()


@pytest.mark.parametrize(
    "method,params,expected_status,mock_avail,mock_expanded,mock_sched",
    [
        ("GET", {"inst": "test"}, 400, None, None, None),
        (
            "GET",
            {"inst": "test", "t0": d(0).isoformat(), "t1": d(2).isoformat()},
            200,
            [{"id": "1", "fields": {"test": "data"}}],
            ["expanded_data"],
            [{"fields": {"Start Time": d(1).isoformat(), "Rejected": False}}],
        ),
        (
            "PUT",
            {
                "rec": "1",
                "t0": d(0).isoformat(),
                "t1": d(1).isoformat(),
                "inst_id": "inst1",
            },
            200,
            None,
            None,
            None,
        ),
        ("PUT", {"t0": d(0).isoformat()}, 400, None, None, None),
        (
            "PUT",
            {"t0": d(1).isoformat(), "t1": d(0).isoformat()},
            400,
            None,
            None,
            None,
        ),
        ("DELETE", {"rec": "1"}, 200, None, None, None),
        ("POST", {}, 405, None, None, None),
    ],
)
def test_inst_availability(
    inst_client,
    mocker,
    method,
    params,
    expected_status,
    mock_avail,
    mock_expanded,
    mock_sched,
):
    """Test instructor availability endpoint with various methods and parameters"""
    if method == "GET":
        if mock_avail is not None:
            mocker.patch.object(
                instructor.airtable,
                "get_instructor_availability",
                return_value=mock_avail,
            )
            mocker.patch.object(
                instructor.airtable,
                "expand_instructor_availability",
                return_value=mock_expanded,
            )
            mocker.patch.object(
                instructor.airtable,
                "get_class_automation_schedule",
                return_value=mock_sched,
            )
            mocker.patch.object(
                instructor.booked,
                "get_reservations",
                return_value={},
            )
        resp = inst_client.get("/instructor/calendar/availability", query_string=params)
    elif method == "PUT":
        mocker.patch.object(
            instructor.airtable,
            "update_availability" if "rec" in params else "add_availability",
            return_value=(200, {"result": "success"}),
        )
        resp = inst_client.put("/instructor/calendar/availability", json=params)
    elif method == "DELETE":
        mocker.patch.object(
            instructor.airtable,
            "delete_availability",
            return_value=(200, {"result": "deleted"}),
        )
        resp = inst_client.delete("/instructor/calendar/availability", json=params)
    else:
        resp = inst_client.open(
            "/instructor/calendar/availability",
            method=method,
            json=params if method != "GET" else None,
            query_string=params if method == "GET" else None,
        )

    if resp.status_code != expected_status:
        raise RuntimeError(
            f"Want ({expected_status}, _), got ({resp.status_code}, {resp.data})"
        )
    if expected_status == 200:
        if method == "GET":
            assert "availability" in resp.json
            assert "schedule" in resp.json
        else:
            assert "result" in resp.json


def test_availability_reservations(mocker, inst_client):
    """Specifically test reservation parsing"""
    mocker.patch.object(
        instructor.airtable,
        "get_instructor_availability",
        return_value=[{"id": "1", "fields": {"test": "data"}}],
    )
    mocker.patch.object(
        instructor.airtable,
        "expand_instructor_availability",
        return_value=["expanded_data"],
    )
    mocker.patch.object(
        instructor.airtable,
        "get_class_automation_schedule",
        return_value=[{"fields": {"Start Time": d(1).isoformat(), "Rejected": False}}],
    )
    mocker.patch.object(
        instructor.booked,
        "get_reservations",
        return_value={
            "reservations": [
                {
                    "bufferedStartDate": d(0, 16).isoformat(),
                    "bufferedEndDate": d(0, 19).isoformat(),
                    "resourceName": "test tool",
                    "firstName": "First",
                    "lastName": "Last",
                    "referenceNumber": "123",
                }
            ]
        },
    )
    resp = inst_client.get(
        "/instructor/calendar/availability",
        query_string={"inst": "test", "t0": d(0).isoformat(), "t1": d(2).isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json == {
        "availability": mocker.ANY,
        "records": mocker.ANY,
        "schedule": mocker.ANY,
        "reservations": [
            [
                d(0, 16).isoformat(),
                d(0, 19).isoformat(),
                "test tool",
                "First Last",
                "https://reserve.protohaven.org/Web/reservation/?rn=123",
            ],
        ],
    }


def test_run_scheduler_success(mocker, inst_client):
    """Test successful scheduler run"""
    mock_result = {"schedule": "test_schedule"}
    mock_score = 95.5
    mocker.patch.object(
        instructor, "solve_with_env", return_value=(mock_result, mock_score)
    )

    response = inst_client.post("/instructor/run_scheduler", json={"test": "data"})

    assert response.status_code == 200
    assert response.json == {"result": mock_result, "score": mock_score}


def test_run_scheduler_no_availability(mocker, inst_client):
    """Test scheduler run with no availability"""
    mocker.patch.object(
        instructor, "solve_with_env", side_effect=instructor.NoAvailabilityError()
    )

    response = inst_client.post("/instructor/run_scheduler", json={"test": "data"})

    assert response.status_code == 400
    assert "No availability specified" in response.get_data(as_text=True)
