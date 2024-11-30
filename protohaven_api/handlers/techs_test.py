"""Verify proper behavior of tech lead dashboard"""
# pylint: skip-file
import json

import pytest

from protohaven_api.handlers import techs as tl
from protohaven_api.rbac import Role, set_rbac
from protohaven_api.testing import MatchStr, fixture_client, setup_session


@pytest.fixture()
def tech_client(client):
    with client.session_transaction() as session:
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
        return_value={"firstName": "First", "lastName": "Last"},
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
            mocker.call(MatchStr("Seats remaining: 5"), "#instructors", blocking=False),
            mocker.call(MatchStr("Seats remaining: 5"), "#techs", blocking=False),
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
        return_value={"firstName": "First", "lastName": "Last"},
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
            mocker.call(MatchStr("Seats remaining: 5"), "#instructors", blocking=False),
            mocker.call(MatchStr("Seats remaining: 5"), "#techs", blocking=False),
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
