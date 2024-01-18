"""Unit tests for role-based authentication"""
from unittest.mock import MagicMock

from protohaven_api import rbac


def test_require_login_redirect(monkeypatch):
    """require_login() redirects when not logged in"""
    monkeypatch.setattr("protohaven_api.rbac.session", {})
    monkeypatch.setattr("protohaven_api.rbac.request", MagicMock(url="Testurl"))
    monkeypatch.setattr("protohaven_api.rbac.redirect", lambda x: x)
    monkeypatch.setattr("protohaven_api.rbac.url_for", lambda x: x)

    fn = rbac.require_login(lambda: "called")
    result = fn()
    assert result == "login_user_neon_oauth"


def test_require_login_ok(monkeypatch):
    """require_login() executes function when logged in"""
    monkeypatch.setattr("protohaven_api.rbac.session", {"neon_id": "foo"})
    fn = rbac.require_login(lambda: "called")
    result = fn()
    assert result == "called"
