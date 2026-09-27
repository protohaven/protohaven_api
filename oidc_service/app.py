"""Flask application that exposes a minimal OIDC provider.

The provider delegates authentication to Neon CRM using the existing
``protohaven_api.oauth`` module. Account data is fetched through the existing
``protohaven_api.integrations.neon_base`` module, which means this service
reuses the repository's Neon integration rather than reimplementing it.

Web handlers in this module stay intentionally thin. Client validation lives in
``clients.py``, claim building and Neon account fetching in ``claims.py``,
authorization-code handling in ``auth_codes.py``, request/response helpers in
``web.py``, and JWT/key handling in ``tokens.py``.
"""

import logging
import secrets
import threading

from flask import Flask, Response, jsonify, redirect, request, session

from oidc_service import auth_codes, claims, clients, tokens, web
from protohaven_api import oauth
from protohaven_api.config import get_config


def create_app():  # pylint: disable=too-many-statements
    """Create and configure the OIDC provider Flask app."""
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)

    server_mode = str(get_config("general/server_mode", "dev")).lower()

    configured_secret = get_config("oidc/session_secret")
    if clients.unset(configured_secret):
        if server_mode == "prod":
            raise RuntimeError(
                "oidc/session_secret is required in production; refusing to "
                "generate an ephemeral Flask session key"
            )
        app.secret_key = secrets.token_hex(32)
        app.logger.warning(
            "No oidc/session_secret configured; using an ephemeral Flask session key."
        )
    else:
        app.secret_key = configured_secret

    issuer = str(get_config("oidc/issuer", "http://127.0.0.1:5002")).rstrip("/")
    if clients.unset(issuer):
        issuer = "http://127.0.0.1:5002"
    app.config["OIDC_ISSUER"] = issuer
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=issuer.startswith("https://"),
    )

    app.config["OIDC_CLIENTS"] = clients.parse_clients(get_config("oidc/clients", []))
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
    app.extensions["oidc_used_codes_lock"] = threading.Lock()

    private_key_pem = get_config("oidc/rsa_private_key")
    app.config["OIDC_PRIVATE_KEY_PEM"] = (
        None if clients.unset(private_key_pem) else private_key_pem
    )
    tokens.setup_signing_keys(app, allow_ephemeral=server_mode != "prod")

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
                "scopes_supported": list(tokens.SUPPORTED_SCOPES),
                "claims_supported": list(claims.USERINFO_CLAIM_NAMES),
                "token_endpoint_auth_methods_supported": [
                    "client_secret_post",
                    "client_secret_basic",
                ],
            }
        )

    @app.get("/jwks.json")
    def jwks():
        """Serve the public JWKS used by clients to validate ID tokens."""
        return jsonify({"keys": [tokens.public_jwk(app)]})

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
        scopes = web.requested_scopes()

        if response_type != "code":
            return web.oidc_json_error(
                "unsupported_response_type", "Only response_type=code is supported"
            )
        if "openid" not in scopes:
            return web.oidc_json_error("invalid_scope", "The openid scope is required")

        client = clients.find_client(app, client_id)
        if client is None:
            return web.oidc_json_error("unauthorized_client", "Unknown client_id")
        if not redirect_uri or not clients.valid_redirect_uri(client, redirect_uri):
            return web.oidc_json_error(
                "invalid_request", "redirect_uri is not registered for this client"
            )

        session["oidc_request"] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "nonce": nonce,
        }
        return redirect(oauth.prep_request(f"{issuer}/callback"))

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
            return web.oidc_redirect_error(
                redirect_uri,
                "access_denied",
                request.args.get("error_description", neon_error),
                state,
            )

        code = request.args.get("code")
        if not code:
            return web.oidc_redirect_error(
                redirect_uri, "invalid_request", "Missing authorization code", state
            )

        try:
            neon_token = oauth.retrieve_token(f"{issuer}/callback", code)
            neon_id = neon_token.get("access_token")
            if not neon_id:
                raise RuntimeError(
                    f"Neon token response did not contain access_token: {neon_token}"
                )
            member = claims.fetch_neon_member(neon_id)
            user_claims = claims.member_claims(member, oidc_request["scope"].split())
            auth_code = auth_codes.create_auth_code(app, oidc_request, user_claims)
        except Exception:  # pylint: disable=broad-exception-caught
            app.logger.exception("Failed to complete Neon OIDC authentication")
            return web.oidc_redirect_error(
                redirect_uri, "server_error", "Neon authentication failed", state
            )

        return redirect(
            web.url_with_params(
                redirect_uri,
                {"code": auth_code, **web.state_params(state)},
            )
        )

    @app.post("/token")
    def token():  # pylint: disable=too-many-return-statements
        """Exchange an OIDC authorization code for tokens."""
        if request.form.get("grant_type") != "authorization_code":
            return web.oidc_json_error("unsupported_grant_type", status=400)

        client_id, client_secret = web.client_credentials()
        client = clients.find_client(app, client_id)
        if client is None or not secrets.compare_digest(
            client_secret, client["client_secret"]
        ):
            return web.oidc_json_error("invalid_client", status=401)

        code = request.form.get("code", "")
        redirect_uri = request.form.get("redirect_uri", "")
        if not code:
            return web.oidc_json_error("invalid_request", "Missing authorization code")

        try:
            oidc_request = auth_codes.load_auth_code(app, code)
        except auth_codes.AuthCodeExpired:
            return web.oidc_json_error("invalid_grant", "Authorization code expired")
        except auth_codes.AuthCodeError:
            return web.oidc_json_error("invalid_grant", "Invalid authorization code")

        if oidc_request["client_id"] != client_id:
            return web.oidc_json_error(
                "invalid_grant", "Authorization code client mismatch"
            )
        if oidc_request["redirect_uri"] != redirect_uri:
            return web.oidc_json_error("invalid_grant", "redirect_uri mismatch")

        jti = oidc_request.get("jti")
        with app.extensions["oidc_used_codes_lock"]:
            if jti in app.extensions["oidc_used_codes"]:
                return web.oidc_json_error(
                    "invalid_grant", "Authorization code already used"
                )
            app.extensions["oidc_used_codes"].add(jti)

        scopes = oidc_request["scope"].split()
        user_claims = oidc_request["claims"]
        access_token = tokens.issue_access_token(app, client_id, scopes, user_claims)
        id_token = tokens.issue_id_token(
            app, client_id, oidc_request, user_claims, access_token
        )
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
        token = web.bearer_token()
        if not token:
            return web.oidc_json_error(
                "invalid_token", "Missing bearer token", status=401
            )

        try:
            payload = tokens.decode_access_token(app, token)
        except tokens.JWTError as e:
            return web.oidc_json_error("invalid_token", str(e), status=401)
        return jsonify(claims.userinfo_claims(payload))

    return app
