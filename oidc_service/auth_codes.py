"""Encrypted, short-lived OIDC authorization code helpers.

Authorization codes are bearer credentials, so they must not be forgeable and
should not expose the claims they carry to anyone who can read a browser
history or proxy log. ``itsdangerous`` signing alone would make them tamper-
evident but still Base64-readable; Fernet encrypts and authenticates them.

The encryption key is derived from the OIDC RSA private key rather than the
Flask session secret. That means a leaked session secret allows session forgery
but does not, by itself, allow minting authorization codes with arbitrary
``sub``/``roles`` claims.
"""

import base64
import hashlib
import json
import secrets
import threading
import time

from cryptography.fernet import Fernet, InvalidToken


class AuthCodeError(Exception):
    """Raised when an authorization code is malformed or invalid."""


class AuthCodeExpired(AuthCodeError):
    """Raised when an otherwise valid authorization code has expired."""


class UsedCodeStore:
    """Thread-safe, TTL-cleaned set of already-redeemed authorization code jtis."""

    def __init__(self, ttl_sec: float):
        self.ttl_sec = ttl_sec
        self._used: dict[str, float] = {}
        self._lock = threading.Lock()

    def cleanup(self, now: float | None = None):
        """Remove expired jtis."""
        now = now if now is not None else time.time()
        with self._lock:
            expired = [jti for jti, expires in self._used.items() if expires <= now]
            for jti in expired:
                del self._used[jti]

    def contains_and_mark(self, jti: str, now: float | None = None) -> bool:
        """Return True if the jti is already used; otherwise mark it used."""
        now = now if now is not None else time.time()
        with self._lock:
            expired = [jti for jti, expires in self._used.items() if expires <= now]
            for expired_jti in expired:
                del self._used[expired_jti]
            if jti in self._used:
                return True
            self._used[jti] = now + self.ttl_sec
            return False


def _fernet(app) -> Fernet:
    """Return the Fernet instance used for authorization codes."""
    key = hashlib.sha256(app.config["OIDC_PRIVATE_KEY"]).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def create_auth_code(app, oidc_request, claims):
    """Create a short-lived, encrypted authorization code."""
    data = dict(oidc_request)
    data["claims"] = claims
    data["auth_time"] = int(time.time())
    data["jti"] = secrets.token_urlsafe(24)
    payload = json.dumps(data, separators=(",", ":")).encode("utf8")
    return _fernet(app).encrypt(payload).decode("ascii")


def load_auth_code(app, code):
    """Decrypt, validate, and TTL-check an authorization code."""
    try:
        fernet = _fernet(app)
        token = code.encode("ascii")
        timestamp = fernet.extract_timestamp(token)
    except (InvalidToken, UnicodeEncodeError) as exc:
        raise AuthCodeError(str(exc)) from exc

    if time.time() - timestamp > app.config["OIDC_AUTH_CODE_TTL"]:
        raise AuthCodeExpired("Authorization code expired")

    try:
        raw = fernet.decrypt(token)
    except InvalidToken as exc:
        raise AuthCodeError(str(exc)) from exc

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AuthCodeError(str(exc)) from exc
