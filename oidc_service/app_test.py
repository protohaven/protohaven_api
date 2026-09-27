"""Tests for the standalone OIDC provider."""

# pylint: disable=protected-access

from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import jwt
import pytest

from oidc_service import app as oidc_app

ISSUER = "http://127.0.0.1:5002"
REDIRECT_URI = "http://localhost:6875/oidc/callback"


def _config():
    return {
        "oidc/issuer": ISSUER,
        "oidc/session_secret": "test-session-secret",  # pragma: allowlist secret
        "oidc/rsa_private_key": None,
        "oidc/access_token_ttl_sec": 3600,
        "oidc/id_token_ttl_sec": 3600,
        "oidc/auth_code_ttl_sec": 600,
        "oidc/clients": [
            {
                "client_id": "bookstack",
                "client_secret": "bookstack-secret",  # pragma: allowlist secret
                "redirect_uris": [REDIRECT_URI],
            }
        ],
    }


@pytest.fixture(name="app")
def fixture_app(mocker):
    """Create a Flask OIDC app with a deterministic test config."""
    cfg = _config()
    mocker.patch.object(
        oidc_app,
        "get_config",
        side_effect=lambda path, default=None: cfg.get(path, default),
    )
    app = oidc_app.create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(name="client")
def fixture_client(app):
    """Provide a Flask test client."""
    return app.test_client()


def _member():
    member = MagicMock()
    member.neon_id = "1234"
    member.name = "Ada Lovelace"
    member.email = "ada@example.com"
    member.clearances = ["FRG: Forge"]
    member.roles = [{"name": "Admin"}, {"name": "Instructor"}]
    member.account_current_membership_status = "Active"
    return member


def _oidc_request():
    return {
        "client_id": "bookstack",
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile email roles clearances",
        "state": "xyz",
        "nonce": "abc",
    }


def _auth_code(app, claims=None):
    return oidc_app._create_auth_code(
        app, _oidc_request(), claims or {"sub": "1234", "neon_id": "1234"}
    )


def test_openid_configuration(client):
    """Discovery metadata points at this service."""
    rep = client.get("/.well-known/openid-configuration")
    assert rep.status_code == 200
    data = rep.get_json()
    assert data["issuer"] == ISSUER
    assert data["authorization_endpoint"] == f"{ISSUER}/authorize"
    assert data["jwks_uri"] == f"{ISSUER}/jwks.json"
    assert "RS256" in data["id_token_signing_alg_values_supported"]


def test_parse_clients_ignores_unsubstituted_env_placeholders():
    """Clients with missing env values are ignored instead of being used."""
    parsed = oidc_app._parse_clients(
        [
            {
                "client_id": "ok",
                "client_secret": "secret",  # pragma: allowlist secret
                "redirect_uris": ["http://localhost/callback"],
            },
            {
                "client_id": "${OIDC_BOOKSTACK_CLIENT_ID}",
                "client_secret": "${OIDC_BOOKSTACK_CLIENT_SECRET}",
                "redirect_uris": ["${OIDC_BOOKSTACK_REDIRECT_URI}"],
            },
        ]
    )
    assert [c["client_id"] for c in parsed] == ["ok"]


def test_jwks_contains_rsa_key(client):
    """JWKS returns a usable RSA public key."""
    rep = client.get("/jwks.json")
    assert rep.status_code == 200
    keys = rep.get_json()["keys"]
    assert len(keys) == 1
    assert keys[0]["kty"] == "RSA"
    assert keys[0]["alg"] == "RS256"


def test_authorize_redirects_to_neon_and_stores_request(mocker, client):
    """A valid OIDC request is stored and forwarded to Neon CRM."""
    mocker.patch.object(oidc_app.oauth, "prep_request", return_value="http://neon/auth")

    rep = client.get(
        "/authorize",
        query_string={
            "client_id": "bookstack",
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "openid profile email",
            "state": "xyz",
            "nonce": "abc",
        },
    )

    assert rep.status_code == 302
    assert rep.location == "http://neon/auth"
    with client.session_transaction() as session:
        stored = session["oidc_request"]
        assert stored["client_id"] == "bookstack"
        assert stored["redirect_uri"] == REDIRECT_URI
        assert stored["scope"] == "openid profile email"


def test_authorize_rejects_unknown_client(client):
    """Authorization rejects clients that are not configured."""
    rep = client.get(
        "/authorize",
        query_string={
            "client_id": "unknown",
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "openid",
        },
    )
    assert rep.status_code == 400
    assert rep.get_json()["error"] == "unauthorized_client"


def test_callback_redirects_with_signed_code(mocker, app, client):
    """Neon callback fetches the member and returns an OIDC code."""
    mocker.patch.object(
        oidc_app.oauth, "retrieve_token", return_value={"access_token": "1234"}
    )
    mocker.patch.object(oidc_app, "_fetch_neon_member", return_value=_member())
    with client.session_transaction() as session:
        session["oidc_request"] = _oidc_request()

    rep = client.get("/callback?code=NEON_CODE")

    assert rep.status_code == 302
    location = urlparse(rep.location)
    assert location.scheme == "http"
    assert location.netloc == "localhost:6875"
    assert location.path == "/oidc/callback"
    params = parse_qs(location.query)
    assert params["state"] == ["xyz"]
    code = params["code"][0]
    decoded = oidc_app._load_auth_code(app, code)
    assert decoded["claims"]["sub"] == "1234"
    assert decoded["claims"]["roles"] == ["Admin", "Instructor"]
    assert decoded["claims"]["email"] == "ada@example.com"


def test_token_endpoint_returns_signed_jwts(app, client):
    """The token endpoint exchanges a valid code for OIDC tokens."""
    code = _auth_code(app)

    rep = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": "bookstack",
            "client_secret": "bookstack-secret",  # pragma: allowlist secret
        },
    )

    assert rep.status_code == 200
    data = rep.get_json()
    assert data["token_type"] == "Bearer"
    id_token = jwt.decode(
        data["id_token"],
        app.config["OIDC_PUBLIC_KEY"],
        algorithms=["RS256"],
        audience="bookstack",
    )
    assert id_token["iss"] == ISSUER
    assert id_token["sub"] == "1234"
    assert id_token["nonce"] == "abc"


def test_token_endpoint_rejects_code_reuse(app, client):
    """Authorization codes are single-use."""
    code = _auth_code(app)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": "bookstack",
        "client_secret": "bookstack-secret",  # pragma: allowlist secret
    }
    assert client.post("/token", data=data).status_code == 200
    assert client.post("/token", data=data).status_code == 400


def test_userinfo_returns_claims_for_access_token(app, client):
    """Userinfo accepts the access token issued by the token endpoint."""
    code = _auth_code(app)
    token_rep = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": "bookstack",
            "client_secret": "bookstack-secret",  # pragma: allowlist secret
        },
    )
    access_token = token_rep.get_json()["access_token"]

    rep = client.get("/userinfo", headers={"Authorization": f"Bearer {access_token}"})

    assert rep.status_code == 200
    assert rep.get_json()["sub"] == "1234"
