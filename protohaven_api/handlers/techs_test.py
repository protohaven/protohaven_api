"""Verify proper behavior of tech lead dashboard"""

# pylint: skip-file
import json

import pytest

from protohaven_api.handlers import techs as tl
from protohaven_api.rbac import Role, set_rbac
from protohaven_api.testing import MatchStr, d, fixture_client, setup_session


@pytest.fixture()
def tech_client(client):
    with client.session_transaction() as session:
        session["neon_id"] = "12345"
        session["neon_account"] = {
            "accountCustomFields": [
                {"name": "API server role", "optionValues": [{"name": "Shop Tech"}]},
            ],
            "primaryContact": {
                "firstName": "First",
                "lastName": "Last",
                "email1": "foo@bar.com",
            },
        }
    return client


def test_techs_all_status(client, mocker):
    setup_session(client, [Role.SHOP_TECH_LEAD])
    mocker.patch.object(tl.neon, "fetch_techs_list", return_value=[])
    mocker.patch.object(tl.airtable, "get_shop_tech_time_off", return_value=[])
    response = client.get("/techs/list")
    rep = json.loads(response.data.decode("utf8"))
    assert rep == {"tech_lead": True, "techs": []}


def test_tech_update(client, mocker):
    setup_session(client, [Role.SHOP_TECH_LEAD])
    mocker.patch.object(
        tl.neon, "set_tech_custom_fields", return_value=(mocker.MagicMock(), None)
    )
    client.post("/techs/update", json={"id": "123", "interest": "stuff"})
    tl.neon.set_tech_custom_fields.assert_called_with("123", interest="stuff")


def test_techs_enroll(client, mocker):
    setup_session(client, [Role.SHOP_TECH_LEAD])
    mocker.patch.object(
        tl.neon, "patch_member_role", return_value=(mocker.MagicMock(), None)
    )
    client.post("/techs/enroll", json={"email": "a@b.com", "enroll": True})
    tl.neon.patch_member_role.assert_called_with("a@b.com", Role.SHOP_TECH, True)


def test_techs_event_registration_success_register(client, mocker):
    """Test successful registration"""
    setup_session(client, [Role.SHOP_TECH])
    mocker.patch.object(tl.neon, "register_for_event", return_value={"key": "value"})
    mocker.patch.object(tl.neon, "delete_single_ticket_registration")
    mocker.patch.object(tl.comms, "send_discord_message")
    mocker.patch.object(
        tl.neon_base,
        "fetch_account",
        return_value=({"firstName": "First", "lastName": "Last"}, True),
    )
    mocker.patch.object(
        tl.neon,
        "fetch_event",
        return_value={"name": "Event Name", "startDate": "YYYY-MM-DD", "capacity": 6},
    )
    mocker.patch.object(
        tl.neon,
        "fetch_attendees",
        return_value=[{"accountId": 1, "registrationStatus": "SUCCEEDED"}],
    )
    assert client.post(
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


def test_techs_event_registration_success_unregister(client, mocker):
    """Test successful unregistration"""
    setup_session(client, [Role.SHOP_TECH])
    mocker.patch.object(tl.neon, "register_for_event")
    mocker.patch.object(tl.neon, "delete_single_ticket_registration", return_value=b"")
    mocker.patch.object(tl.comms, "send_discord_message")
    mocker.patch.object(
        tl.neon_base,
        "fetch_account",
        return_value=({"firstName": "First", "lastName": "Last"}, True),
    )
    mocker.patch.object(
        tl.neon,
        "fetch_event",
        return_value={"name": "Event Name", "startDate": "YYYY-MM-DD", "capacity": 6},
    )
    mocker.patch.object(
        tl.neon,
        "fetch_attendees",
        return_value=[{"accountId": 1, "registrationStatus": "SUCCEEDED"}],
    )
    assert client.post(
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


def test_techs_event_registration_missing_args(client, mocker):
    """Test registration with missing arguments"""
    setup_session(client, [Role.SHOP_TECH])
    mocker.patch.object(tl.neon, "register_for_event")
    mocker.patch.object(tl.neon, "delete_single_ticket_registration")
    assert client.post("/techs/event", json={}).status_code == 400
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
            },
            {
                "id": "17631",
                "startDate": d(0).strftime("%Y-%m-%d"),
                "startTime": "10:00",
                "capacity": 10,
                "name": "Private Event",
            },
            {
                "id": "124",
                "startDate": d(-5).strftime("%Y-%m-%d"),
                "startTime": "10:00",
                "capacity": 10,
                "name": "Event B, too early",
            },
        ],
    )
    mocker.patch.object(
        tl.neon,
        "fetch_attendees",
        side_effect=[[{"accountId": "1", "registrationStatus": "SUCCEEDED"}], []],
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
    assert response.json == [
        {
            "attendees": ["1"],
            "capacity": 10,
            "id": "123",
            "name": "Event A",
            "start": "Wed, 01 Jan 2025 15:00:00 GMT",
            "supply_cost": 10,
            "ticket_id": "t1",
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
    tl.neon.register_for_event.assert_called_once_with("12345", 123, 456)
    tl._notify_registration.assert_called_once_with("12345", 123, "register")
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
    tl.neon.delete_single_ticket_registration.assert_called_once_with("12345", 123)
    tl._notify_registration.assert_called_once_with("12345", 123, "unregister")


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
