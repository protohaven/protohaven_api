"""Verify proper behavior of tech lead dashboard"""
# pylint: skip-file
import json

import pytest

from protohaven_api.handlers import techs as tl
from protohaven_api.main import app
from protohaven_api.rbac import Role, set_rbac


@pytest.fixture()
def client():
    set_rbac(False)
    return app.test_client()


def test_techs_all_status(client, mocker):
    mocker.patch.object(tl.neon, "fetch_techs_list", return_value=[])
    mocker.patch.object(tl.airtable, "get_shop_tech_time_off", return_value=[])
    response = client.get("/techs/list")
    rep = json.loads(response.data.decode("utf8"))
    assert rep == {"tech_lead": True, "techs": []}


def test_tech_update(client, mocker):
    mocker.patch.object(
        tl.neon, "set_tech_custom_fields", return_value=(mocker.MagicMock(), None)
    )
    client.post("/techs/update", json={"id": "123", "interest": "stuff"})
    tl.neon.set_tech_custom_fields.assert_called_with("123", interest="stuff")


def test_techs_enroll(client, mocker):
    mocker.patch.object(
        tl.neon, "patch_member_role", return_value=(mocker.MagicMock(), None)
    )
    client.post("/techs/enroll", json={"email": "a@b.com", "enroll": True})
    tl.neon.patch_member_role.assert_called_with("a@b.com", Role.SHOP_TECH, True)
