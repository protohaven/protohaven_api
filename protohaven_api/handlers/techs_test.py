"""Verify proper behavior of tech lead dashboard"""

# pylint: skip-file
import json

import pytest

from protohaven_api.handlers import techs as tl
from protohaven_api.rbac import Role, set_rbac
from protohaven_api.testing import MatchStr, d, fixture_client, setup_session


@pytest.fixture()
def tech_client(client):
    setup_session(client, [Role.SHOP_TECH])
    return client


@pytest.fixture()
def lead_client(client):
    setup_session(client, [Role.SHOP_TECH_LEAD])
    return client


def test_techs_all_status(lead_client, mocker):
    mocker.patch.object(tl.neon, "fetch_techs_list", return_value=[])
    mocker.patch.object(tl.airtable, "get_all_tech_bios", return_value=[])
    response = lead_client.get("/techs/list")
    rep = json.loads(response.data.decode("utf8"))
    assert rep == {"tech_lead": True, "techs": []}


def test_techs_picture_url(lead_client, mocker):
    """Ensure that both Nocodb and Airtable URL paths are observed"""
    mocker.patch.object(
        tl.neon,
        "fetch_techs_list",
        return_value=[
            {"email": "asdf"},
        ],
    )
    mocker.patch.object(
        tl.airtable,
        "get_all_tech_bios",
        return_value=[
            {
                "fields": {
                    "Email": "asdf",
                    "Picture": [{"thumbnails": {"large": {"url": "want"}}}],
                }
            },
        ],
    )
    response = lead_client.get("/techs/list")
    rep = json.loads(response.data.decode("utf8"))
    assert rep == {
        "tech_lead": True,
        "techs": [
            {"bio": {}, "email": "asdf", "picture": "want"},
        ],
    }

    mocker.patch.object(
        tl.airtable,
        "get_all_tech_bios",
        return_value=[
            {
                "fields": {
                    "Email": "asdf",
                    "Picture": [{"thumbnails": {"large": {"signedPath": "want"}}}],
                }
            },
        ],
    )
    response = lead_client.get("/techs/list")
    rep = json.loads(response.data.decode("utf8"))
    assert rep == {
        "tech_lead": True,
        "techs": [
            {"bio": {}, "email": "asdf", "picture": "http://localhost:8080/want"},
        ],
    }


def test_tech_update(lead_client, mocker):
    mocker.patch.object(
        tl.neon, "set_tech_custom_fields", return_value=(mocker.MagicMock(), None)
    )
    lead_client.post("/techs/update", json={"id": "123", "interest": "stuff"})
    tl.neon.set_tech_custom_fields.assert_called_with("123", interest="stuff")


def test_techs_enroll(lead_client, mocker):
    mocker.patch.object(
        tl.neon, "patch_member_role", return_value=(mocker.MagicMock(), None)
    )
    lead_client.post("/techs/enroll", json={"email": "a@b.com", "enroll": True})
    tl.neon.patch_member_role.assert_called_with("a@b.com", Role.SHOP_TECH, True)


def test_techs_event_registration_success_register(tech_client, mocker):
    """Test successful registration"""
    mocker.patch.object(tl.neon, "register_for_event", return_value={"key": "value"})
    mocker.patch.object(tl.neon, "delete_single_ticket_registration")
    mocker.patch.object(tl.comms, "send_discord_message")
    mocker.patch.object(
        tl.neon_base,
        "fetch_account",
        return_value=(
            {"primaryContact": {"firstName": "First", "lastName": "Last"}},
            True,
        ),
    )
    mocker.patch.object(
        tl.neon,
        "fetch_event",
        return_value={
            "name": "Event Name",
            "eventDates": {"startDate": "YYYY-MM-DD", "startTime": "HH:MM"},
            "maximumAttendees": 6,
        },
    )
    mocker.patch.object(
        tl.neon,
        "fetch_attendees",
        return_value=[{"accountId": 1, "registrationStatus": "SUCCEEDED"}],
    )
    assert tech_client.post(
        "/techs/event",
        json={
            "event_id": "test_event",
            "ticket_id": "test_ticket",
            "action": "register",
        },
    ).json == {"key": "value"}
    tl.neon.register_for_event.assert_called_with(1234, "test_event", "test_ticket")
    tl.neon.delete_single_ticket_registration.assert_not_called()
    tl.comms.send_discord_message.assert_has_calls(
        [
            mocker.call(MatchStr("5 seat"), "#instructors", blocking=False),
            mocker.call(MatchStr("5 seat"), "#techs", blocking=False),
        ]
    )


def test_techs_event_registration_success_unregister(tech_client, mocker):
    """Test successful unregistration"""
    mocker.patch.object(tl.neon, "register_for_event")
    mocker.patch.object(tl.neon, "delete_single_ticket_registration", return_value=b"")
    mocker.patch.object(tl.comms, "send_discord_message")
    mocker.patch.object(
        tl.neon_base,
        "fetch_account",
        return_value=(
            {"primaryContact": {"firstName": "First", "lastName": "Last"}},
            True,
        ),
    )
    mocker.patch.object(
        tl.neon,
        "fetch_event",
        return_value={
            "name": "Event Name",
            "eventDates": {"startDate": "YYYY-MM-DD"},
            "maximumAttendees": 6,
        },
    )
    mocker.patch.object(
        tl.neon,
        "fetch_attendees",
        return_value=[{"accountId": 1, "registrationStatus": "SUCCEEDED"}],
    )
    assert tech_client.post(
        "/techs/event",
        json={
            "event_id": "test_event",
            "ticket_id": "test_ticket",
            "action": "unregister",
        },
    ).json == {"status": "ok"}
    tl.neon.register_for_event.assert_not_called()
    tl.neon.delete_single_ticket_registration.assert_called_with(1234, "test_event")
    tl.comms.send_discord_message.assert_has_calls(
        [
            mocker.call(MatchStr("5 seat"), "#instructors", blocking=False),
            mocker.call(MatchStr("5 seat"), "#techs", blocking=False),
        ]
    )


def test_techs_event_registration_missing_args(tech_client, mocker):
    """Test registration with missing arguments"""
    mocker.patch.object(tl.neon, "register_for_event")
    mocker.patch.object(tl.neon, "delete_single_ticket_registration")
    assert tech_client.post("/techs/event", json={}).status_code == 400
    tl.neon.register_for_event.assert_not_called()
    tl.neon.delete_single_ticket_registration.assert_not_called()


def test_techs_forecast_override_post(mocker, tech_client):
    mocker.patch.object(
        tl.airtable, "set_forecast_override", return_value=(200, "Success")
    )
    mocker.patch.object(tl.comms, "send_discord_message")
    response = tech_client.post(
        "/techs/forecast/override",
        json={
            "id": "123",
            "fullname": "John Doe",
            "date": "2023-10-01",
            "ap": "AM",
            "techs": ["Tech1", "Tech2"],
            "email": "john.doe@example.com",
        },
    )
    assert response.status_code == 200
    assert response.data.decode() == "Success"
    tl.comms.send_discord_message.assert_called_once_with(
        MatchStr("Tech1, Tech2"), "#techs", blocking=False
    )


def test_techs_forecast_override_delete(mocker, tech_client):
    mocker.patch.object(tl.airtable, "delete_forecast_override", return_value="Deleted")
    mocker.patch.object(tl.comms, "send_discord_message")
    response = tech_client.delete(
        "/techs/forecast/override",
        json={
            "id": "123",
            "fullname": "John Doe",
            "date": "2023-10-01",
            "ap": "AM",
            "techs": ["Tech3"],
            "orig": ["Tech1", "Tech2"],
        },
    )
    assert response.status_code == 200
    assert response.data.decode() == "Deleted"
    tl.comms.send_discord_message.assert_called_once_with(
        MatchStr("Tech1, Tech2"), "#techs", blocking=False
    )


def test_techs_backfill_events(mocker, tech_client):
    """Test the techs_backfill_events handler for expected output."""
    mocker.patch.object(
        tl.airtable,
        "get_class_automation_schedule",
        return_value=[
            {"fields": {"Neon ID": "123", "Supply Cost (from Class)": [10]}},
            {"fields": {"Neon ID": "17631", "Supply Cost (from Class)": [15]}},
            {"fields": {"Neon ID": "124"}},
        ],
    )
    mocker.patch.object(
        tl.neon,
        "fetch_upcoming_events",
        return_value=[
            {
                "id": "123",
                "startDate": d(0).strftime("%Y-%m-%d"),
                "startTime": "10:00",
                "capacity": 10,
                "name": "Event A",
                "publishEvent": True,
                "enableEventRegistrationForm": True,
            },
            {  # Tech event gets shown even if no registrants
                "id": "999",
                "startDate": d(0).strftime("%Y-%m-%d"),
                "startTime": "10:00",
                "capacity": 10,
                "name": f"{tl.TECH_ONLY_PREFIX} no registants",
                "publishEvent": False,
                "enableEventRegistrationForm": True,
            },
            {  # No registrants event gets hidden as it's not paid off
                "id": "999",
                "startDate": d(0).strftime("%Y-%m-%d"),
                "startTime": "10:00",
                "capacity": 10,
                "name": "Upcoming event with no registants",
                "publishEvent": True,
                "enableEventRegistrationForm": True,
            },
            {
                "id": "17631",
                "startDate": d(0).strftime("%Y-%m-%d"),
                "startTime": "10:00",
                "capacity": 10,
                "name": "Private Event",
                "publishEvent": True,
                "enableEventRegistrationForm": True,
            },
            {
                "id": "124",
                "startDate": d(-5).strftime("%Y-%m-%d"),
                "startTime": "10:00",
                "capacity": 10,
                "name": "Event B, too early",
                "publishEvent": True,
                "enableEventRegistrationForm": True,
            },
        ],
    )
    mocker.patch.object(
        tl.neon,
        "fetch_attendees",
        side_effect=[
            [{"accountId": "1", "registrationStatus": "SUCCEEDED"}],
            [],
            [],
            [],
        ],
    )
    mocker.patch.object(
        tl.neon,
        "fetch_tickets",
        return_value=[
            {"id": "t1", "name": "Single Registration"},
            {"id": "t2", "name": "Other Ticket"},
        ],
    )
    mocker.patch.object(tl, "tznow", return_value=d(0))

    response = tech_client.get("/techs/events")
    assert response.status_code == 200
    assert response.json["events"] == [
        {
            "attendees": ["1"],
            "capacity": 10,
            "id": "123",
            "name": "Event A",
            "start": "Wed, 01 Jan 2025 15:00:00 GMT",
            "supply_cost": 10,
            "ticket_id": "t1",
        },
        {
            "attendees": [],
            "capacity": 10,
            "id": "999",
            "name": "(SHOP TECH ONLY) no registants",
            "start": "Wed, 01 Jan 2025 15:00:00 GMT",
            "supply_cost": 0,
            "ticket_id": None,
        },
    ]


def test_techs_event_registration_register(mocker, tech_client):
    """Test techs_event_registration for registering"""
    mocker.patch.object(tl.neon, "register_for_event", return_value={"status": "ok"})
    mocker.patch.object(tl.comms, "send_discord_message")
    mocker.patch.object(tl, "_notify_registration")
    mocker.patch.object(tl.neon, "delete_single_ticket_registration")

    rep = tech_client.post(
        "/techs/event", json={"event_id": 123, "ticket_id": 456, "action": "register"}
    )
    assert rep.json == {"status": "ok"}
    tl.neon.register_for_event.assert_called_once_with(1234, 123, 456)
    tl._notify_registration.assert_called_once_with(1234, 123, "register")
    tl.neon.delete_single_ticket_registration.assert_not_called()


def test_techs_event_registration_unregister(mocker, tech_client):
    """Test techs_event_registration for registering"""
    mocker.patch.object(tl.neon, "register_for_event")
    mocker.patch.object(tl.comms, "send_discord_message")
    mocker.patch.object(tl, "_notify_registration")
    mocker.patch.object(
        tl.neon, "delete_single_ticket_registration", return_value={"status": "ok"}
    )

    rep = tech_client.post(
        "/techs/event", json={"event_id": 123, "ticket_id": 456, "action": "unregister"}
    )
    assert rep.json == {"status": "ok"}
    tl.neon.register_for_event.assert_not_called()
    tl.neon.delete_single_ticket_registration.assert_called_once_with(1234, 123)
    tl._notify_registration.assert_called_once_with(1234, 123, "unregister")


def test_techs_area_leads(mocker, tech_client):
    """Tests the techs_area_leads function"""
    mock_areas = ["Area1", "Area2"]
    mock_techs = [
        {"name": "Tech1", "area_lead": "Area1, ExtraArea"},
        {"name": "Tech2", "area_lead": "Area2"},
        {"name": "Tech3", "area_lead": "NonExistentArea"},
    ]
    mocker.patch.object(
        tl,
        "_fetch_tool_states_and_areas",
        return_value=(None, mock_areas),
    )
    mocker.patch.object(tl.neon, "fetch_techs_list", return_value=mock_techs)

    response = tech_client.get("/techs/area_leads")
    assert response.status_code == 200

    expected_response = {
        "area_leads": {
            "Area1": [{"name": "Tech1", "area_lead": "Area1, ExtraArea"}],
            "Area2": [{"name": "Tech2", "area_lead": "Area2"}],
        },
        "other_leads": {
            "ExtraArea": [{"name": "Tech1", "area_lead": "Area1, ExtraArea"}],
            "NonExistentArea": [{"name": "Tech3", "area_lead": "NonExistentArea"}],
        },
    }

    assert response.json == expected_response


def test_new_tech_event(mocker, lead_client):
    """Test new tech-only event creation"""
    mocker.patch.object(tl, "tznow", return_value=d(0))
    mock_create_event = mocker.patch.object(
        tl.neon_base, "create_event", return_value={}
    )

    # Test valid event creation
    response = lead_client.post(
        "/techs/new_event",
        json={
            "name": "Test Event",
            "start": d(1, 14).isoformat(),
            "hours": 2,
            "capacity": 10,
        },
    )
    assert response.status_code == 200
    mock_create_event.assert_called_once_with(
        name=f"{tl.TECH_ONLY_PREFIX} Test Event",
        desc="Tech-only event; created via api.protohaven.org/techs dashboard",
        start=d(1, 14),
        end=d(1, 16),
        max_attendees=10,
        dry_run=False,
        published=False,
        registration=True,
        free=True,
    )

    # Test empty name
    response = lead_client.post(
        "/techs/new_event",
        json={"name": "", "start": "2025-01-01T12:00:00", "hours": 2, "capacity": 10},
    )
    assert response.status_code == 401
    assert response.data.decode() == "name field is required"

    # Test invalid start time (past)
    response = lead_client.post(
        "/techs/new_event",
        json={
            "name": "Test Event",
            "start": "2020-01-01T12:00:00",
            "hours": 2,
            "capacity": 10,
        },
    )
    assert response.status_code == 401
    assert response.data.decode() == MatchStr("must be set to a valid date")

    # Test invalid start time (outside business hours)
    response = lead_client.post(
        "/techs/new_event",
        json={
            "name": "Test Event",
            "start": "2025-01-01T08:00:00",
            "hours": 2,
            "capacity": 10,
        },
    )
    assert response.status_code == 401
    assert response.data.decode() == MatchStr("must be set to a valid date")
    # Test invalid capacity (negative)
    response = lead_client.post(
        "/techs/new_event",
        json={
            "name": "Test Event",
            "start": "2025-01-01T12:00:00",
            "hours": 2,
            "capacity": -1,
        },
    )
    assert response.status_code == 401
    assert response.data.decode() == "capacity field invalid"


def test_rm_tech_event(mocker, lead_client):
    """Test deleting a techs-only event in Neon"""
    eid = "12345"
    mock_event = {"id": eid, "name": tl.TECH_ONLY_PREFIX + "Test Event"}

    mocker.patch.object(tl.neon, "fetch_event", return_value=mock_event)
    mocker.patch.object(tl.neon, "set_event_scheduled_state", return_value={})

    response = lead_client.post("/techs/rm_event", json={"eid": eid})
    assert response.status_code == 200

    tl.neon.fetch_event.assert_called_once_with(eid)
    tl.neon.set_event_scheduled_state.assert_called_once_with(eid, scheduled=False)


def test_rm_tech_event_missing_eid(mocker, lead_client):
    """Test deleting a techs-only event with missing eid"""
    response = lead_client.post("/techs/rm_event", json={"eid": ""})
    assert response.status_code == 401
    assert response.data.decode("utf-8") == "eid field required"


def test_rm_tech_event_not_found(mocker, lead_client):
    """Test deleting a non-existent techs-only event"""
    eid = "12345"
    mocker.patch.object(tl.neon, "fetch_event", return_value=None)

    response = lead_client.post("/techs/rm_event", json={"eid": eid})
    assert response.status_code == 404
    assert response.data.decode("utf-8") == f"event with eid {eid} not found"


def test_rm_tech_event_non_tech_only(mocker, lead_client):
    """Test deleting a non-tech-only event"""
    eid = "12345"
    mock_event = {"id": eid, "name": "Test Event"}

    mocker.patch.object(tl.neon, "fetch_event", return_value=mock_event)

    response = lead_client.post("/techs/rm_event", json={"eid": eid})
    assert response.status_code == 400
    assert response.data.decode("utf-8") == MatchStr(
        "cannot delete a non-tech-only event"
    )


def test_techs_members(mocker, tech_client):
    """Test fetching member sign-ins for techs view"""
    mock_signins = [{"id": "1", "name": "Test User"}]
    mocker.patch.object(tl.airtable, "get_signins_between", return_value=mock_signins)
    mocker.patch.object(tl, "tznow", return_value=d(0))
    mocker.patch.object(tl.dateparser, "parse", return_value=d(1))

    rep = tech_client.get("/techs/members?start=2024-01-01")
    assert rep.json == mock_signins
    tl.airtable.get_signins_between.assert_called_once_with(
        d(1).replace(hour=0, minute=0, second=0), None
    )

    got = tech_client.get("/techs/members")
    assert rep.json == mock_signins
    tl.airtable.get_signins_between.assert_called_with(
        d(0).replace(hour=0, minute=0, second=0), None
    )
