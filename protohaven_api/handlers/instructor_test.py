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


def test_dashboard_schedule(mocker):
    """Confirm behavior of shown and hidden schedule items for the instructor dashboard"""

    def _sched(_id, email=TEST_EMAIL, start=now, confirmed=None, rejected=None):
        """Create and return a fake Airtable schedule record"""
        end = start + datetime.timedelta(hours=3)
        return mocker.MagicMock(
            spec=True,
            schedule_id=_id,
            instructor_email=email,
            sessions=[(start, end)],
            start_time=start,
            end_time=end,
            confirmed=confirmed,
            rejected=rejected,
        )

    mocker.patch.object(instructor, "tznow", return_value=d(0))
    mocker.patch.object(
        instructor.airtable,
        "get_class_automation_schedule",
        return_value=[
            _sched(
                "Unconfirmed, too close HIDDEN",
                confirmed=None,
                start=d(instructor.HIDE_UNCONFIRMED_DAYS_AHEAD - 1),
            ),
            _sched(
                "Email mismatch",
                email="nomatch",
                start=d(instructor.HIDE_UNCONFIRMED_DAYS_AHEAD + 1),
            ),
            _sched(
                "Unconfirmed, not too close",
                confirmed=None,
                start=d(instructor.HIDE_UNCONFIRMED_DAYS_AHEAD + 1),
            ),
            _sched(
                "Confirmed, too old HIDDEN",
                confirmed=d(0),
                start=d(-instructor.HIDE_CONFIRMED_DAYS_AFTER - 1),
            ),
            _sched(
                "Confirmed, after run, not too old",
                confirmed=now,
                start=d(-instructor.HIDE_CONFIRMED_DAYS_AFTER + 1),
            ),
            _sched(
                "Rejected",
                rejected=now,
                start=d(-instructor.HIDE_UNCONFIRMED_DAYS_AHEAD + 1),
            ),
            _sched("Bad email", confirmed=now, start=now, email="bad@bad.com"),
        ],
    )
    got = {g.schedule_id for g in instructor.get_dashboard_schedule_sorted(TEST_EMAIL)}
    assert got == {"Unconfirmed, not too close", "Confirmed, after run, not too old"}


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


def test_instructor_about_from_session(inst_client, mocker):
    mocker.patch.object(instructor.neon, "search_members_by_email", return_value=[{}])
    mocker.patch.object(instructor, "get_instructor_readiness")
    rep = inst_client.get("/instructor/about")
    assert rep.status_code == 200
    instructor.neon.search_members_by_email.assert_called_with(
        "foo@bar.com", fields=mocker.ANY
    )


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
                spec=True,
                neon_id=12345,
                email="a@b.com",
                account_current_membership_status="Inactive",
                fname="First",
                lname="Last",
                discord_user=None,
            ),
            mocker.MagicMock(
                spec=True,
                neon_id=12346,
                email="a@b.com",
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
        "email": "a@b.com",
        "email_status": "2 duplicate accounts in Neon",
        "capabilities_listed": "missing",
        "paperwork": "unknown",
        "profile_img": None,
        "bio": None,
    }


def test_get_instructor_readiness_all_ok(mocker):
    mocker.patch.object(instructor, "airtable")
    instructor.airtable.fetch_instructor_capabilities.return_value = {
        "id": "inst_id",
        "classes": [1, 2, 3],
        "w9": "<file>",
        "direct_deposit": "<file>",
        "profile_pic": "<url>",
        "bio": "test bio",
    }
    result = instructor.get_instructor_readiness(
        [
            mocker.MagicMock(
                neon_id=12345,
                email="a@b.com",
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
        "email_status": "OK",
        "email": "a@b.com",
        "capabilities_listed": "OK",
        "classes": [1, 2, 3],
        "paperwork": "OK",
        "profile_img": "<url>",
        "bio": "test bio",
    }


def test_instructor_class_supply_req(mocker, inst_client):
    """Test marking supplies as missing or confirmed for a class"""
    mcls = mocker.MagicMock(
        instructor_name="Instructor Name",
        start_time=d(0),
    )
    mcls.name = "Class Name"

    mocker.patch.object(instructor.airtable, "get_scheduled_class", return_value=mcls)
    msched = mocker.MagicMock()
    msched.as_response.return_value = "Foo"
    mocker.patch.object(
        instructor.airtable, "mark_schedule_supply_request", return_value=msched
    )
    mocker.patch.object(instructor.comms, "send_discord_message")

    response = inst_client.post(
        "/instructor/class/supply_req", json={"eid": "class123", "missing": True}
    )

    assert response.status_code == 200
    instructor.airtable.get_scheduled_class.assert_called_once_with(
        "class123", raw=False
    )
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


def test_log_quiz_submission(mocker, inst_client):
    """Test logging quiz submission to airtable"""
    mock_insert = mocker.patch.object(
        instructor.airtable, "insert_quiz_result", return_value=(None, None)
    )

    test_data = {
        "data": {"Question1": "Answer1", "Question2": "Answer2"},
        "tool_codes": ["LS1", "LS2"],
        "email": "foo@bar.com",
        "points_to_pass": "5",
        "points_scored": "3",
        "submitted": d(0).isoformat(),
    }

    response = inst_client.post("/instructor/clearance_quiz", json=test_data)
    mock_insert.assert_called_once_with(
        submitted=d(0),
        email="foo@bar.com",
        tool_codes=["LS1", "LS2"],
        data={"Question1": "Answer1", "Question2": "Answer2"},
        points_scored=3,
        points_to_pass=5,
    )
    assert response.status_code == 200
