"""Verify proper behavior of onboarding pages"""
# pylint: skip-file
import datetime
import json

import pytest

from protohaven_api import rbac
from protohaven_api.handlers import onboarding
from protohaven_api.main import app


@pytest.fixture()
def client():
    rbac.set_rbac(False)
    return app.test_client()


def test_onboarding_role_assignment_get(client):
    result = client.get("/onboarding/role_assignment")
    rep = json.loads(result.data.decode("utf8"))
    for r in ["Instructor", "Private Instructor", "Shop Tech"]:
        assert r in rep


def test_onboarding_role_assignment_post(client, mocker):
    mocker.patch.object(onboarding.neon, "patch_member_role")
    result = client.post(
        "/onboarding/role_assignment",
        json={
            "email": "foo@bar.com",
            "roles": {"Instructor": True, "Shop Tech": False},
        },
    )
    rep = json.loads(result.data.decode("utf8"))
    assert "Updated 2 role(s)" in rep["status"]
    calls = [
        (c.args[1]["name"], c.args[2])
        for c in onboarding.neon.patch_member_role.mock_calls
    ]
    assert calls == [("Instructor", True), ("Shop Tech", False)]


def test_onboarding_role_assignment_fails_if_privileged(client, mocker):
    """Confirm that privileged roles (e.g. ADMIN) cannot be assigned
    by onboarders"""
    mocker.patch.object(onboarding.neon, "patch_member_role")
    result = client.post(
        "/onboarding/role_assignment",
        json={"email": "foo@bar.com", "roles": {"Admin": True}},
    )
    assert result.status_code == 401
    onboarding.neon.patch_member_role.assert_not_called()
