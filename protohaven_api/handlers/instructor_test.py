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
TEST_ID = "12345"
now = datetime.datetime.now()


def test_dashboard_schedule(mocker):
    """Confirm behavior of shown and hidden schedule items for the instructor dashboard"""

    def _sched(_id, email=TEST_EMAIL, start=now, confirmed=None, rejected=None):
        """Create and return a fake Airtable schedule record"""
        start = start.astimezone(tz)
        end = start + datetime.timedelta(hours=3)
        return mocker.MagicMock(
            spec=True,
            schedule_id=_id,
            instructor_id=None,
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
    got = {
        g.schedule_id
        for g in instructor.get_dashboard_schedule_sorted(TEST_ID, TEST_EMAIL)
    }
    assert got == {"Unconfirmed, not too close", "Confirmed, after run, not too old"}


def test_instructor_class_attendees(inst_client, mocker):
    # Create a mock Attendee object
    mock_attendee = mocker.MagicMock()
    mock_attendee.neon_raw_data = {"accountId": 123}
    mock_attendee.eventbrite_data = {}
    mock_attendee.neon_id = 123
    mock_attendee.email = "attendee@example.com"
    mock_attendee.fname = "John"
    mock_attendee.name = "John Doe"
    mock_attendee.valid = True

    mocker.patch.object(
        instructor.eauto, "fetch_attendees", return_value=[mock_attendee]
    )
    mocker.patch.object(
        instructor.neon.neon_base,
        "fetch_account",
        return_value=mocker.MagicMock(email="member@example.com"),
    )
    result = inst_client.get("/instructor/class/attendees?id=12345")
    assert result.status_code == 200
    rep = json.loads(result.data.decode("utf8"))
    # Check the structure matches what the handler returns
    assert len(rep) == 1
    assert rep[0]["neon_id"] == 123
    assert rep[0]["email"] == "attendee@example.com"
    assert rep[0]["member_email"] == "member@example.com"
    assert rep[0]["neon_raw_data"] == {"accountId": 123}


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
    mocker.patch.object(
        instructor.neon,
        "search_members_by_email",
        return_value=[mocker.MagicMock(neon_id="12345")],
    )

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
    # Verify fetch_instructor_capabilities was called with neon_id
    instructor.airtable.fetch_instructor_capabilities.assert_called_once_with(12345)
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
    # Verify fetch_instructor_capabilities was called with neon_id
    instructor.airtable.fetch_instructor_capabilities.assert_called_once_with(12345)
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


def test_instructor_submissions(mocker, inst_client):
    """Test the instructor submissions handler"""
    # Mock the sheets module
    mock_sheets = mocker.patch.object(instructor, "sheets")

    # Create mock submissions data
    now = datetime.datetime.now()
    mock_submissions = [
        {
            "Timestamp": now,
            "Email Address": "foo@bar.com",
            "Neon Event ID (please ignore)": "EVENT123",
            "Class Name": "Woodworking 101",
            "Students Passed": "3",
        },
        {
            "Timestamp": now + datetime.timedelta(hours=1),
            "Email Address": "foo@bar.com",
            "Neon Event ID (please ignore)": "EVENT456",
            "Class Name": "Metalworking 101",
            "Students Passed": "5",
        },
        {
            "Timestamp": now + datetime.timedelta(hours=2),
            "Email Address": "foo@bar.com",
            "Neon Event ID (please ignore)": "EVENT123",  # Same event, different submission
            "Class Name": "Woodworking 101 - Advanced",
            "Students Passed": "2",
        },
        {
            "Timestamp": now + datetime.timedelta(hours=3),
            "Email Address": "other@bar.com",  # Different instructor
            "Neon Event ID (please ignore)": "EVENT789",
            "Class Name": "Ceramics 101",
            "Students Passed": "2",
        },
        {
            "Timestamp": now + datetime.timedelta(hours=4),
            "Email Address": "foo@bar.com",
            # Missing Neon Event ID
            "Class Name": "3D Printing 101",
            "Students Passed": "4",
        },
    ]

    # Set up the mock to return our test data
    mock_sheets.get_instructor_submissions_raw.return_value = mock_submissions

    # Test with logged-in user (foo@bar.com)
    response = inst_client.get("/instructor/submissions")
    assert response.status_code == 200

    # Parse the response
    data = json.loads(response.data)

    # Should have 2 event IDs for foo@bar.com
    assert len(data) == 2

    # Check that EVENT123 and EVENT456 are in the results
    assert "EVENT123" in data
    assert "EVENT456" in data

    # Verify the data structure - each event ID should have a list of timestamps
    assert isinstance(data["EVENT123"], list)
    assert len(data["EVENT123"]) == 2  # Two submissions for EVENT123
    # Check that we have timestamps (they will be serialized as strings by Flask)
    assert isinstance(data["EVENT123"][0], str)
    assert isinstance(data["EVENT123"][1], str)

    assert isinstance(data["EVENT456"], list)
    assert len(data["EVENT456"]) == 1
    assert isinstance(data["EVENT456"][0], str)

    # Test with email parameter (same as logged-in user)
    response = inst_client.get("/instructor/submissions?email=foo@bar.com")
    assert response.status_code == 200

    # Test with email parameter (different user - should fail without admin role)
    response = inst_client.get("/instructor/submissions?email=other@bar.com")
    assert response.status_code == 401

    # Test with admin role accessing other user's submissions
    mocker.patch.object(rbac, "get_roles", return_value=[rbac.Role.ADMIN["name"]])
    response = inst_client.get("/instructor/submissions?email=other@bar.com")
    assert response.status_code == 200
    data = json.loads(response.data)
    # Should have 1 event ID for other@bar.com
    assert len(data) == 1
    assert "EVENT789" in data
    assert isinstance(data["EVENT789"], list)
    assert len(data["EVENT789"]) == 1
    assert isinstance(data["EVENT789"][0], str)


def test_instructor_list(mocker, inst_client):
    """Test instructor list endpoint"""
    from protohaven_api.integrations.models import Member

    m = Member.from_neon_search(
        {
            "Email 1": "instructor@test.com",
            "First Name": "Test",
            "Last Name": "Instructor",
            "Account ID": 456,
        }
    )
    mocker.patch.object(instructor.neon, "search_members_with_role", return_value=[m])
    mocker.patch.object(instructor.airtable, "get_all_instructor_bios", return_value=[])
    # Mock airtable_base.get_all_records for class templates
    mocker.patch.object(instructor.airtable_base, "get_all_records", return_value=[])

    # Mock education lead role
    mocker.patch.object(instructor, "am_role", return_value=True)
    mocker.patch.object(instructor, "am_lead_role", return_value=True)

    response = inst_client.get("/instructor/list")
    assert response.json["instructors"][0] == {
        "clearances": [],
        "email": "instructor@test.com",
        "neon_id": 456,
        "name": "Test Instructor",
        "volunteer_bio": None,
        "volunteer_picture": None,
    }
    assert response.json["education_lead"] == True
    assert "capabilities" in response.json
    assert "classes" in response.json


def test_instructor_enroll(inst_client, mocker):
    """Test instructor enrollment endpoint"""
    # Mock the patch_member_role function
    mock_response = (mocker.MagicMock(), None)
    mocker.patch.object(
        instructor.neon, "patch_member_role", return_value=mock_response
    )

    # Test enrollment - should fail because inst_client doesn't have education lead role
    response = inst_client.post(
        "/instructor/enroll", json={"neon_id": "123", "enroll": True}
    )

    # Should return 401 or redirect since user doesn't have education lead role
    assert response.status_code in [401, 302]


def test_instructor_enroll_with_education_lead(client, mocker):
    """Test instructor enrollment endpoint with education lead role"""
    from protohaven_api.integrations.models import Role
    from protohaven_api.testing import setup_session

    # Setup session with education lead role
    setup_session(client, [Role.EDUCATION_LEAD])

    # Mock the patch_member_role function
    mock_response = (mocker.MagicMock(), None)
    mocker.patch.object(
        instructor.neon, "patch_member_role", return_value=mock_response
    )

    # Test enrollment
    response = client.post(
        "/instructor/enroll", json={"neon_id": "123", "enroll": True}
    )

    instructor.neon.patch_member_role.assert_called_with(
        "123", instructor.Role.INSTRUCTOR, True
    )
    assert response.status_code == 200


def test_instructor_enroll_create_account(client, mocker):
    """Test instructor enrollment with account creation"""
    from protohaven_api.integrations.models import Role
    from protohaven_api.testing import setup_session

    # Setup session with education lead role
    setup_session(client, [Role.EDUCATION_LEAD])

    # Mock functions
    mocker.patch.object(instructor.neon, "create_member", return_value="789")
    mock_response = (mocker.MagicMock(), None)
    mocker.patch.object(
        instructor.neon, "patch_member_role", return_value=mock_response
    )

    # Test enrollment with account creation
    response = client.post(
        "/instructor/enroll",
        json={
            "name": "New Instructor",
            "email": "new@test.com",
            "enroll": True,
            "create_account": True,
        },
    )

    instructor.neon.create_member.assert_called_with("New Instructor", "new@test.com")
    instructor.neon.patch_member_role.assert_called_with(
        "789", instructor.Role.INSTRUCTOR, True
    )
    assert response.status_code == 200


def test_instructor_enroll_missing_fields(client, mocker):
    """Test instructor enrollment with missing fields for account creation"""
    from protohaven_api.integrations.models import Role
    from protohaven_api.testing import setup_session

    # Setup session with education lead role
    setup_session(client, [Role.EDUCATION_LEAD])

    # Test enrollment with missing name and email
    response = client.post(
        "/instructor/enroll", json={"enroll": True, "create_account": True}
    )

    assert response.status_code == 400
    assert "error" in response.json
    assert "Name and email are required" in response.json["error"]
