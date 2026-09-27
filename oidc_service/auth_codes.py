"""Signed, short-lived OIDC authorization code helpers."""

import secrets
import time

from itsdangerous import URLSafeTimedSerializer


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
