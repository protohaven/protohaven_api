"""Flask application that exposes a minimal OIDC provider.

The provider delegates authentication to Neon CRM using the existing
``protohaven_api.oauth`` module. Account data is fetched through the existing
``protohaven_api.integrations.neon_base`` module, which means this service
reuses the repository's Neon integration rather than reimplementing it.
"""

import base64
import hashlib
import logging
import secrets
import time
from urllib.parse import urlencode

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, Response, jsonify, redirect, request, session
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

from protohaven_api import oauth
from protohaven_api.config import get_config

log = logging.getLogger("oidc_service")

SUPPORTED_SCOPES = ("openid", "profile", "email", "roles", "clearances")


def _now() -> int:
    """Return the current Unix time as an integer."""
    return int(time.time())


def _base64url_long(value: int) -> str:
    """Encode an integer as unpadded base64url bytes."""
    length = (value.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode()


def _at_hash(token: str) -> str:
    """Return the OIDC at_hash value for an access token."""
    digest = hashlib.sha256(token.encode("utf8")).digest()
    return base64.urlsafe_b64encode(digest[:16]).rstrip(b"=").decode()


def _unset(value):
    """Return True for empty config values and unsubstituted env placeholders."""
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or stripped.startswith("${")
    return False


def _parse_clients(raw_clients):
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
            if not _unset(uri)
        ]
        if not _unset(client_id) and not _unset(client_secret) and redirect_uris:
            result.append(
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": redirect_uris,
                }
            )
    return result


def _generate_rsa_key():
    """Generate an ephemeral RSA keypair for token signing."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def _setup_signing_keys(app):
    """Load or generate the RSA keypair used to sign JWTs."""
    private_pem = get_config("oidc/rsa_private_key")
    if _unset(private_pem):
        private_pem = None
    if isinstance(private_pem, str):
        private_pem = private_pem.replace("\\n", "\n").encode("utf8")
    if not private_pem:
        private_pem, _ = _generate_rsa_key()
        app.logger.warning(
            "No oidc/rsa_private_key configured; generated an ephemeral RSA key. "
            "Configure a persistent key when running in production."
        )

    private_key = serialization.load_pem_private_key(private_pem, password=None)
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    numbers = public_key.public_numbers()
    app.config["OIDC_PRIVATE_KEY"] = private_pem
    app.config["OIDC_PUBLIC_KEY"] = public_pem
    app.config["OIDC_PUBLIC_KEY_OBJ"] = public_key
    app.config["OIDC_KID"] = (
        "oidc-" + hashlib.sha256(str(numbers.n).encode("utf8")).hexdigest()[:16]
    )


def _public_jwk(app):
    """Return the public JWK for the active signing key."""
    numbers = app.config["OIDC_PUBLIC_KEY_OBJ"].public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "kid": app.config["OIDC_KID"],
        "alg": "RS256",
        "n": _base64url_long(numbers.n),
        "e": _base64url_long(numbers.e),
    }


def _auth_code_serializer(app) -> URLSafeTimedSerializer:
    """Return the serializer used for OIDC authorization codes."""
    return URLSafeTimedSerializer(app.secret_key, salt="oidc-auth-code")


def _load_auth_code(app, code):
    """Decode and validate an authorization code."""
    return _auth_code_serializer(app).loads(
        code, max_age=app.config["OIDC_AUTH_CODE_TTL"]
    )


def _create_auth_code(app, oidc_request, claims):
    """Create a short-lived, signed authorization code."""
    data = dict(oidc_request)
    data["claims"] = claims
    data["auth_time"] = _now()
    data["jti"] = secrets.token_urlsafe(24)
    return _auth_code_serializer(app).dumps(data)


def _find_client(app, client_id):
    """Return the configured client with the given client_id, if any."""
    for client in app.config["OIDC_CLIENTS"]:
        if client["client_id"] == client_id:
            return client
    return None


def _valid_redirect_uri(client, redirect_uri):
    """Return True when redirect_uri is registered for the client."""
    return redirect_uri in client["redirect_uris"]


def _fetch_neon_member(neon_id):
    """Fetch a Protohaven member from Neon using the shared integration."""
    from protohaven_api.integrations import (  # pylint: disable=import-outside-toplevel
        neon_base,
    )

    return neon_base.fetch_account(neon_id, required=True)


def _member_claims(member, scopes):
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


def _sign_jwt(app, payload, ttl):
    """Create a signed RS256 JWT."""
    now = _now()
    token_payload = {
        **payload,
        "iss": app.config["OIDC_ISSUER"],
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(
        token_payload,
        app.config["OIDC_PRIVATE_KEY"],
        algorithm="RS256",
        headers={"kid": app.config["OIDC_KID"]},
    )


def _issue_access_token(app, client_id, scopes, claims):
    """Issue an OIDC access token."""
    return _sign_jwt(
        app,
        {
            "sub": claims["sub"],
            "aud": client_id,
            "scope": " ".join(scopes),
            **claims,
        },
        app.config["OIDC_ACCESS_TOKEN_TTL"],
    )


def _issue_id_token(app, client_id, oidc_request, claims, access_token):
    """Issue an OIDC ID token."""
    payload = {
        "sub": claims["sub"],
        "aud": client_id,
        "auth_time": oidc_request["auth_time"],
        "at_hash": _at_hash(access_token),
        **claims,
    }
    if oidc_request.get("nonce"):
        payload["nonce"] = oidc_request["nonce"]
    return _sign_jwt(app, payload, app.config["OIDC_ID_TOKEN_TTL"])


def _oidc_redirect_error(redirect_uri, error, description, state=None):
    """Redirect back to the client with an OIDC error."""
    params = {"error": error, "error_description": description}
    if state is not None:
        params["state"] = state
    return redirect(f"{redirect_uri}?{urlencode(params)}")


def _oidc_json_error(error, description=None, status=400):
    """Return a JSON OAuth/OIDC error response."""
    payload = {"error": error}
    if description:
        payload["error_description"] = description
    return jsonify(payload), status


def _requested_scopes():
    """Parse the requested OIDC scopes from the request."""
    return [s for s in request.values.get("scope", "openid").split() if s]


def _bearer_token():
    """Extract a bearer token from the Authorization header, if present."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer ") :].strip()


def _userinfo_claims(payload):
    """Return only the user-identity claims from a JWT payload."""
    allowed = {
        "sub",
        "name",
        "email",
        "preferred_username",
        "neon_id",
        "roles",
        "clearances",
        "member",
    }
    return {k: payload[k] for k in allowed if k in payload}


def _client_credentials():
    """Read client credentials from HTTP Basic or the token request body."""
    if request.authorization and request.authorization.type == "basic":
        return request.authorization.username, request.authorization.password or ""
    return request.form.get("client_id", ""), request.form.get("client_secret", "")


def create_app():  # pylint: disable=too-many-statements
    """Create and configure the OIDC provider Flask app."""
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)

    configured_secret = get_config("oidc/session_secret")
    app.secret_key = (
        None if _unset(configured_secret) else configured_secret
    ) or secrets.token_hex(32)
    if _unset(configured_secret):
        app.logger.warning(
            "No oidc/session_secret configured; using an ephemeral Flask session key."
        )

    issuer = str(get_config("oidc/issuer", "http://127.0.0.1:5002")).rstrip("/")
    if _unset(issuer):
        issuer = "http://127.0.0.1:5002"
    app.config["OIDC_ISSUER"] = issuer
    app.config["OIDC_CLIENTS"] = _parse_clients(get_config("oidc/clients", []))
    if not app.config["OIDC_CLIENTS"]:
        app.logger.warning(
            "No OIDC clients configured; all authorization requests will fail."
        )
    app.config["OIDC_ACCESS_TOKEN_TTL"] = int(
        get_config("oidc/access_token_ttl_sec", 3600)
    )
    app.config["OIDC_ID_TOKEN_TTL"] = int(get_config("oidc/id_token_ttl_sec", 3600))
    app.config["OIDC_AUTH_CODE_TTL"] = int(get_config("oidc/auth_code_ttl_sec", 600))
    app.extensions["oidc_used_codes"] = set()

    _setup_signing_keys(app)

    @app.get("/.well-known/openid-configuration")
    def openid_configuration():
        """Serve OIDC discovery metadata."""
        return jsonify(
            {
                "issuer": issuer,
                "authorization_endpoint": f"{issuer}/authorize",
                "token_endpoint": f"{issuer}/token",
                "userinfo_endpoint": f"{issuer}/userinfo",
                "jwks_uri": f"{issuer}/jwks.json",
                "response_types_supported": ["code"],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "scopes_supported": list(SUPPORTED_SCOPES),
                "claims_supported": [
                    "sub",
                    "name",
                    "email",
                    "preferred_username",
                    "neon_id",
                    "roles",
                    "clearances",
                    "member",
                ],
                "token_endpoint_auth_methods_supported": [
                    "client_secret_post",
                    "client_secret_basic",
                ],
            }
        )

    @app.get("/jwks.json")
    def jwks():
        """Serve the public JWKS used by clients to validate ID tokens."""
        return jsonify({"keys": [_public_jwk(app)]})

    @app.get("/health")
    def health():
        """Simple health check."""
        return jsonify({"status": "ok"})

    @app.get("/authorize")
    def authorize():
        """Start an OIDC authorization request by redirecting to Neon CRM."""
        client_id = request.args.get("client_id", "")
        redirect_uri = request.args.get("redirect_uri", "")
        response_type = request.args.get("response_type", "")
        state = request.args.get("state")
        nonce = request.args.get("nonce")
        scopes = _requested_scopes()

        if response_type != "code":
            return _oidc_json_error(
                "unsupported_response_type", "Only response_type=code is supported"
            )
        if "openid" not in scopes:
            return _oidc_json_error("invalid_scope", "The openid scope is required")

        client = _find_client(app, client_id)
        if client is None:
            return _oidc_json_error("unauthorized_client", "Unknown client_id")
        if not redirect_uri or not _valid_redirect_uri(client, redirect_uri):
            return _oidc_json_error(
                "invalid_request", "redirect_uri is not registered for this client"
            )

        session["oidc_request"] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "nonce": nonce,
        }
        neon_redirect_uri = f"{issuer}/callback"
        return redirect(oauth.prep_request(neon_redirect_uri))

    @app.get("/callback")
    def neon_callback():
        """Handle the return from Neon CRM and mint an OIDC authorization code."""
        oidc_request = session.pop("oidc_request", None)
        if not oidc_request:
            return Response(
                "Missing OIDC authorization request. Please restart authorization.",
                status=400,
            )

        redirect_uri = oidc_request["redirect_uri"]
        state = oidc_request.get("state")
        neon_error = request.args.get("error")
        if neon_error:
            return _oidc_redirect_error(
                redirect_uri,
                "access_denied",
                request.args.get("error_description", neon_error),
                state,
            )

        code = request.args.get("code")
        if not code:
            return _oidc_redirect_error(
                redirect_uri, "invalid_request", "Missing authorization code", state
            )

        try:
            neon_token = oauth.retrieve_token(f"{issuer}/callback", code)
            neon_id = neon_token.get("access_token")
            if not neon_id:
                raise RuntimeError(
                    f"Neon token response did not contain access_token: {neon_token}"
                )
            member = _fetch_neon_member(neon_id)
            claims = _member_claims(member, oidc_request["scope"].split())
            auth_code = _create_auth_code(app, oidc_request, claims)
        except Exception:  # pylint: disable=broad-exception-caught
            app.logger.exception("Failed to complete Neon OIDC authentication")
            return _oidc_redirect_error(
                redirect_uri, "server_error", "Neon authentication failed", state
            )

        params = {"code": auth_code}
        if state is not None:
            params["state"] = state
        return redirect(f"{redirect_uri}?{urlencode(params)}")

    @app.post("/token")
    def token():  # pylint: disable=too-many-return-statements
        """Exchange an OIDC authorization code for tokens."""
        if request.form.get("grant_type") != "authorization_code":
            return _oidc_json_error("unsupported_grant_type", status=400)

        client_id, client_secret = _client_credentials()
        client = _find_client(app, client_id)
        if client is None or not secrets.compare_digest(
            client_secret, client["client_secret"]
        ):
            return _oidc_json_error("invalid_client", status=401)

        code = request.form.get("code", "")
        redirect_uri = request.form.get("redirect_uri", "")
        if not code:
            return _oidc_json_error("invalid_request", "Missing authorization code")

        try:
            oidc_request = _load_auth_code(app, code)
        except SignatureExpired:
            return _oidc_json_error("invalid_grant", "Authorization code expired")
        except BadData:
            return _oidc_json_error("invalid_grant", "Invalid authorization code")

        if oidc_request["client_id"] != client_id:
            return _oidc_json_error(
                "invalid_grant", "Authorization code client mismatch"
            )
        if oidc_request["redirect_uri"] != redirect_uri:
            return _oidc_json_error("invalid_grant", "redirect_uri mismatch")

        jti = oidc_request.get("jti")
        if jti in app.extensions["oidc_used_codes"]:
            return _oidc_json_error("invalid_grant", "Authorization code already used")
        app.extensions["oidc_used_codes"].add(jti)

        scopes = oidc_request["scope"].split()
        claims = oidc_request["claims"]
        access_token = _issue_access_token(app, client_id, scopes, claims)
        id_token = _issue_id_token(app, client_id, oidc_request, claims, access_token)
        return jsonify(
            {
                "access_token": access_token,
                "id_token": id_token,
                "token_type": "Bearer",
                "expires_in": app.config["OIDC_ACCESS_TOKEN_TTL"],
                "scope": oidc_request["scope"],
            }
        )

    @app.get("/userinfo")
    @app.post("/userinfo")
    def userinfo():
        """Return claims for the supplied access token."""
        token = _bearer_token()
        if not token:
            return _oidc_json_error("invalid_token", "Missing bearer token", status=401)

        audiences = [c["client_id"] for c in app.config["OIDC_CLIENTS"]]
        decode_kwargs = {"algorithms": ["RS256"]}
        if audiences:
            decode_kwargs["audience"] = audiences
        try:
            payload = jwt.decode(
                token,
                app.config["OIDC_PUBLIC_KEY"],
                **decode_kwargs,
            )
        except jwt.PyJWTError as e:
            return _oidc_json_error("invalid_token", str(e), status=401)
        return jsonify(_userinfo_claims(payload))

    return app
