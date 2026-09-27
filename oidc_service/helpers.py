"""Non-Flask helpers used by the OIDC web handlers."""

import secrets
import time
from urllib.parse import urlencode

from flask import jsonify, redirect, request
from itsdangerous import URLSafeTimedSerializer

from protohaven_api.integrations import neon_base

USERINFO_CLAIM_NAMES = (
    "sub",
    "name",
    "email",
    "preferred_username",
    "neon_id",
    "roles",
    "clearances",
    "member",
)


def unset(value):
    """Return True for empty config values and unsubstituted env placeholders."""
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or stripped.startswith("${")
    return False


def parse_clients(raw_clients):
    """Convert config clients into a list of valid client dicts."""
    result = []
    for client in raw_clients or []:
        if not isinstance(client, dict):
            continue
        client_id = str(client.get("client_id", "")).strip()
        client_secret = str(client.get("client_secret", "")).strip()
        redirect_uris = [
            str(uri).strip()
            for uri in (client.get("redirect_uris") or [])
            if not unset(uri)
        ]
        if not unset(client_id) and not unset(client_secret) and redirect_uris:
            result.append(
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": redirect_uris,
                }
            )
    return result


def find_client(app, client_id):
    """Return the configured client with the given client_id, if any."""
    for client in app.config["OIDC_CLIENTS"]:
        if client["client_id"] == client_id:
            return client
    return None


def valid_redirect_uri(client, redirect_uri):
    """Return True when redirect_uri is registered for the client."""
    return redirect_uri in client["redirect_uris"]


def fetch_neon_member(neon_id):
    """Fetch a Protohaven member from Neon using the shared integration."""
    return neon_base.fetch_account(neon_id, required=True)


def member_claims(member, scopes):
    """Build OIDC claims from a Member object.

    ``roles`` and ``clearances`` are always included because hosted services use
    them for authorization. ``name``/``preferred_username`` are released only
    with the ``profile`` scope; ``email`` only with the ``email`` scope.
    """
    scopes = set(scopes or [])
    roles = [r["name"] for r in (member.roles or [])]
    claims = {
        "sub": str(member.neon_id),
        "neon_id": str(member.neon_id),
        "roles": roles,
        "clearances": member.clearances or [],
        "member": member.account_current_membership_status == "Active",
    }
    if "profile" in scopes:
        claims["name"] = member.name
        claims["preferred_username"] = member.email
    if "email" in scopes:
        claims["email"] = member.email
    return claims


def oidc_redirect_error(redirect_uri, error, description, state=None):
    """Redirect back to the client with an OIDC error."""
    return redirect(
        url_with_params(
            redirect_uri,
            {"error": error, "error_description": description, **state_params(state)},
        )
    )


def oidc_json_error(error, description=None, status=400):
    """Return a JSON OAuth/OIDC error response."""
    payload = {"error": error}
    if description:
        payload["error_description"] = description
    return jsonify(payload), status


def requested_scopes():
    """Parse the requested OIDC scopes from the request."""
    return [s for s in request.values.get("scope", "openid").split() if s]


def bearer_token():
    """Extract a bearer token from the Authorization header, if present."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer ") :].strip()


def userinfo_claims(payload):
    """Return only the user-identity claims from a JWT payload."""
    allowed = set(USERINFO_CLAIM_NAMES)
    return {k: payload[k] for k in allowed if k in payload}


def client_credentials():
    """Read client credentials from HTTP Basic or the token request body."""
    if request.authorization and request.authorization.type == "basic":
        return request.authorization.username, request.authorization.password or ""
    return request.form.get("client_id", ""), request.form.get("client_secret", "")


def auth_code_serializer(app) -> URLSafeTimedSerializer:
    """Return the serializer used for OIDC authorization codes."""
    return URLSafeTimedSerializer(app.secret_key, salt="oidc-auth-code")


def create_auth_code(app, oidc_request, claims):
    """Create a short-lived, signed authorization code."""
    data = dict(oidc_request)
    data["claims"] = claims
    data["auth_time"] = int(time.time())
    data["jti"] = secrets.token_urlsafe(24)
    return auth_code_serializer(app).dumps(data)


def load_auth_code(app, code):
    """Decode and validate an authorization code."""
    return auth_code_serializer(app).loads(
        code, max_age=app.config["OIDC_AUTH_CODE_TTL"]
    )


def url_with_params(base, params):
    """Append query parameters to a URL."""
    return f"{base}?{urlencode(params)}"


def state_params(state):
    """Return a one-item dict for state when it is present."""
    return {} if state is None else {"state": state}
