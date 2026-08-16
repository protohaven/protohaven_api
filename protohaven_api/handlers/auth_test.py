"""Tests for auth handlers"""

from protohaven_api.handlers import auth
from protohaven_api.testing import (  # noqa: F401 pylint: disable=unused-import
    fixture_client,
)


def test_user_identity_helpers(mocker):
    """user_email/fullname/id read from the session Neon account"""
    member = mocker.MagicMock()
    member.email = "a@example.com"
    member.name = "Ada Lovelace"
    mocker.patch.object(auth.Member, "from_neon_fetch", return_value=member)
    mocker.patch.object(auth, "session", {"neon_account": {"x": 1}, "neon_id": 123})

    assert auth.user_email() == "a@example.com"
    assert auth.user_fullname() == "Ada Lovelace"
    assert auth.user_id() == "123"


def test_user_identity_helpers_no_data(mocker):
    """Missing session data returns None instead of raising"""
    mocker.patch.object(auth.Member, "from_neon_fetch", side_effect=TypeError)
    mocker.patch.object(auth, "session", {"neon_account": None, "neon_id": None})

    assert auth.user_email() is None
    assert auth.user_fullname() is None
    assert auth.user_id() is None


def test_login_uses_explicit_referrer(mocker, client):
    """A referrer query parameter takes priority for post-login redirect"""
    mocker.patch.object(auth.oauth, "prep_request", return_value="http://oauth")
    rep = client.get("/login?referrer=/classes")
    assert rep.status_code == 302
    assert rep.location == "http://oauth"
    with client.session_transaction() as session:
        assert session["login_referrer"] == "/classes"


def test_login_uses_request_referrer(mocker, client):
    """Without a query param, the Referer header is used"""
    mocker.patch.object(auth.oauth, "prep_request", return_value="http://oauth")
    rep = client.get("/login", headers={"Referer": "http://localhost/referrer"})
    assert rep.status_code == 302
    assert rep.location == "http://oauth"
    with client.session_transaction() as session:
        assert session["login_referrer"] == "http://localhost/referrer"


def test_login_uses_session_referrer(mocker, client):
    """Without query param or Referer, the session value is used"""
    mocker.patch.object(auth.oauth, "prep_request", return_value="http://oauth")
    with client.session_transaction() as session:
        session["redirect_to_login_url"] = "/from-session"
    rep = client.get("/login")
    assert rep.status_code == 302
    assert rep.location == "http://oauth"
    with client.session_transaction() as session:
        assert session["login_referrer"] == "/from-session"


def test_login_defaults_to_root(mocker, client):
    """If all referrer sources are absent, / is used"""
    mocker.patch.object(auth.oauth, "prep_request", return_value="http://oauth")
    rep = client.get("/login")
    assert rep.status_code == 302
    assert rep.location == "http://oauth"
    with client.session_transaction() as session:
        assert session["login_referrer"] == "/"


def test_logout(mocker):
    """logout clears Neon identity from the session"""
    session = {"neon_id": "123", "neon_account": {"x": 1}}
    mocker.patch.object(auth, "session", session)
    assert auth.logout() == "You've been logged out"
    assert session["neon_id"] is None
    assert session["neon_account"] is None


def test_login_with_neon_id(mocker):
    """login_with_neon_id stores the account fetch result in session"""
    session = {}
    mocker.patch.object(auth, "session", session)
    fetch = mocker.patch.object(
        auth.neon_base, "fetch_account", return_value={"individualAccount": {}}
    )
    auth.login_with_neon_id("123")
    assert session["neon_id"] == "123"
    assert session["neon_account"] == {"individualAccount": {}}
    fetch.assert_called_once_with("123", required=True, raw=True)


def test_oauth_redirect(mocker, client):
    """OAuth callback stores the token as neon_id and redirects to login referrer"""
    mocker.patch.object(
        auth.oauth, "retrieve_token", return_value={"access_token": "TOKEN"}
    )
    fetch = mocker.patch.object(
        auth.neon_base, "fetch_account", return_value={"individualAccount": {}}
    )
    with client.session_transaction() as session:
        session["login_referrer"] = "/classes"

    rep = client.get("/oauth_redirect?code=CODE")

    assert rep.status_code == 302
    assert rep.location == "/classes"
    fetch.assert_called_once_with("TOKEN", required=True, raw=True)
    with client.session_transaction() as session:
        assert session["neon_id"] == "TOKEN"
        assert session["neon_account"] == {"individualAccount": {}}


def test_oauth_redirect_defaults_to_root(mocker, client):
    """Without a stored referrer, OAuth redirect lands on /"""
    mocker.patch.object(
        auth.oauth, "retrieve_token", return_value={"access_token": "TOKEN"}
    )
    mocker.patch.object(
        auth.neon_base, "fetch_account", return_value={"individualAccount": {}}
    )
    rep = client.get("/oauth_redirect?code=CODE")
    assert rep.status_code == 302
    assert rep.location == "/"
