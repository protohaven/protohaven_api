"""Unit tests for role-based authentication"""

from unittest.mock import MagicMock

import pytest

from protohaven_api import rbac
from protohaven_api.integrations.models import Role


def test_require_login_redirect(monkeypatch):
    """require_login() redirects when not logged in"""
    rbac.set_rbac(True)
    monkeypatch.setattr("protohaven_api.rbac.session", {})
    monkeypatch.setattr("protohaven_api.rbac.request", MagicMock(url="Testurl"))
    monkeypatch.setattr("protohaven_api.rbac.redirect", lambda x: x)
    monkeypatch.setattr("protohaven_api.rbac.url_for", lambda x: x)

    fn = rbac.require_login(lambda: "called")
    result = fn()
    assert result == "auth.login_user_neon_oauth"


def test_require_login_ok(monkeypatch):
    """require_login() executes function when logged in"""
    rbac.set_rbac(True)
    monkeypatch.setattr("protohaven_api.rbac.session", {"neon_id": "foo"})
    fn = rbac.require_login(lambda: "called")
    result = fn()
    assert result == "called"


def test_require_login_role_techlead_on_tech(mocker):
    """Ensure tech leads can access things that techs can access"""
    rbac.set_rbac(True)
    fn = rbac.require_login_role(Role.SHOP_TECH)(lambda: "called")
    mocker.patch.object(rbac, "get_roles", return_value=[Role.SHOP_TECH["name"]])
    assert fn() == "called"

    mocker.patch.object(rbac, "get_roles", return_value=[Role.SHOP_TECH_LEAD["name"]])
    assert fn() == "called"

    mocker.patch.object(rbac, "get_roles", return_value=[Role.INSTRUCTOR["name"]])
    assert fn() != "called"

    mocker.patch.object(rbac, "get_roles", return_value=["unhandled role"])
    assert fn() != "called"


def test_require_login_role_multiple_args(mocker):
    """Ensure multiple roles can be set for access in `require_login_role`"""
    rbac.set_rbac(True)
    fn = rbac.require_login_role(Role.BOARD_MEMBER, Role.STAFF)(lambda: "called")
    mocker.patch.object(rbac, "get_roles", return_value=[Role.BOARD_MEMBER["name"]])
    assert fn() == "called"

    mocker.patch.object(rbac, "get_roles", return_value=[Role.STAFF["name"]])
    assert fn() == "called"

    mocker.patch.object(rbac, "get_roles", return_value=[Role.INSTRUCTOR["name"]])
    assert fn() != "called"

    mocker.patch.object(rbac, "get_roles", return_value=["unhandled role"])
    assert fn() != "called"


@pytest.mark.parametrize(
    "request_values, request_headers, session_data, expected_roles",
    [
        ("test_api_key", None, None, ["role1", "role2"]),  # With API key request value
        (None, "test_api_key", None, ["role1", "role2"]),  # With API key request header
        (None, None, None, None),  # No auth/session, no roles
        (  # Roles from session
            None,
            None,
            {
                "individualAccount": {
                    "accountCustomFields": [
                        {
                            "name": "API server role",
                            "optionValues": [{"name": "Admin"}, {"name": "Instructor"}],
                        }
                    ]
                }
            },
            ["Admin", "Instructor"],
        ),
        (  # Other custom fields ignored, no roles
            None,
            None,
            {
                "individualAccount": {
                    "accountCustomFields": [
                        {
                            "name": "Some other field",
                            "optionValues": [{"name": "value1"}],
                        }
                    ]
                }
            },
            [],
        ),
    ],
)
def test_get_roles(
    mocker, request_values, request_headers, session_data, expected_roles
):
    """Test the get_roles function extraction from request params/header/session"""
    rmock = mocker.MagicMock(get=lambda: request_values)
    mocker.patch.object(rbac, "request", rmock)
    rmock.values.get.return_value = request_values
    rmock.headers.get.return_value = request_headers
    mocker.patch.object(rbac, "session", mocker.MagicMock(get=lambda _: session_data))
    mocker.patch.object(
        rbac, "get_config", return_value={"test_api_key": ["role1", "role2"]}
    )

    assert rbac.get_roles() == expected_roles


def test_am_role(mocker):
    """Test am_role function"""
    mocker.patch.object(rbac, "is_enabled", return_value=False)
    assert rbac.am_role(Role.ADMIN) is True

    mocker.patch.object(rbac, "is_enabled", return_value=True)
    mocker.patch.object(rbac, "get_roles", return_value=[Role.ADMIN["name"]])
    assert rbac.am_role(Role.ADMIN) is True

    mocker.patch.object(rbac, "is_enabled", return_value=True)
    mocker.patch.object(rbac, "get_roles", return_value=["not_admin"])
    assert rbac.am_role(Role.ADMIN) is False
