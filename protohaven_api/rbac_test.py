"""Unit tests for role-based authentication"""
from unittest.mock import MagicMock

from protohaven_api import rbac
from protohaven_api.rbac import Role


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


def test_require_login_role_multiple_args(mocker):
    """Ensure tech leads can access things that techs can access"""
    rbac.set_rbac(True)
    fn = rbac.require_login_role(Role.BOARD_MEMBER, Role.STAFF)(lambda: "called")
    mocker.patch.object(rbac, "get_roles", return_value=[Role.BOARD_MEMBER["name"]])
    assert fn() == "called"

    mocker.patch.object(rbac, "get_roles", return_value=[Role.STAFF["name"]])
    assert fn() == "called"

    mocker.patch.object(rbac, "get_roles", return_value=[Role.INSTRUCTOR["name"]])
    assert fn() != "called"
