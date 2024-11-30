"""Verify proper behavior of onboarding pages"""
# pylint: skip-file
import datetime
import json

import pytest

from protohaven_api import rbac
from protohaven_api.handlers import onboarding
from protohaven_api.testing import fixture_client


@pytest.fixture()
def onb_client(client):
    with client.session_transaction() as session:
        session["neon_account"] = {
            "accountCustomFields": [
                {"name": "API server role", "optionValues": [{"name": "Onboarding"}]},
            ],
            "primaryContact": {
                "firstName": "First",
                "lastName": "Last",
                "email1": "foo@bar.com",
            },
        }
    return client


def test_onboarding_role_assignment_get(onb_client):
    result = onb_client.get("/onboarding/role_assignment")
    assert result.status_code == 200
    rep = json.loads(result.data.decode("utf8"))
    for r in ["Instructor", "Private Instructor", "Shop Tech"]:
        assert r in rep


def test_onboarding_role_assignment_post(onb_client, mocker):
    mocker.patch.object(onboarding.neon, "patch_member_role", return_value=None)
    result = onb_client.post(
        "/onboarding/role_assignment",
        json={
            "email": "foo@bar.com",
            "roles": {"Instructor": True, "Shop Tech": False},
        },
    )
    assert result.status_code == 200
    rep = json.loads(result.data.decode("utf8"))
    assert "Updated 2 role(s)" in rep["status"]
    calls = [
        (c.args[1]["name"], c.args[2])
        for c in onboarding.neon.patch_member_role.mock_calls
    ]
    assert calls == [("Instructor", True), ("Shop Tech", False)]


def test_onboarding_role_assignment_fails_if_privileged(onb_client, mocker):
    """Confirm that privileged roles (e.g. ADMIN) cannot be assigned
    by onboarders"""
    mocker.patch.object(onboarding.neon, "patch_member_role")
    result = onb_client.post(
        "/onboarding/role_assignment",
        json={"email": "foo@bar.com", "roles": {"Admin": True}},
    )
    assert result.status_code == 401
    onboarding.neon.patch_member_role.assert_not_called()
