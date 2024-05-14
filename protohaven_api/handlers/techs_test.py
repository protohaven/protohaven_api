"""Verify proper behavior of tech lead dashboard"""
# pylint: skip-file
import json

import pytest

from protohaven_api.handlers import tech_lead as tl
from protohaven_api.main import app
from protohaven_api.rbac import Role, set_rbac


@pytest.fixture()
def client():
    set_rbac(False)
    return app.test_client()


def test_tech_lead_all_status(client, mocker):
    mocker.patch.object(tl, "_fetch_techs_list", return_value=[])
    mocker.patch.object(tl, "_fetch_tool_states_and_areas", return_value=([], []))
    mocker.patch.object(tl.airtable, "get_shop_tech_time_off", return_value=[])
    response = client.get("/tech_lead/all_status")
    rep = json.loads(response.data.decode("utf8"))
    assert rep == {"areas": [], "techs": [], "time_off": [], "tool_states": []}


def test_tech_update(client, mocker):
    mocker.patch.object(
        tl.neon, "set_tech_custom_fields", return_value=(mocker.MagicMock(), None)
    )
    client.post("/tech_lead/update", json={"id": "123", "interest": "stuff"})
    tl.neon.set_tech_custom_fields.assert_called_with("123", interest="stuff")


def test_tech_lead_enroll(client, mocker):
    mocker.patch.object(
        tl.neon, "patch_member_role", return_value=(mocker.MagicMock(), None)
    )
    client.post("/tech_lead/enroll", json={"email": "a@b.com", "enroll": True})
    tl.neon.patch_member_role.assert_called_with("a@b.com", Role.SHOP_TECH, True)
