"""JWT creation and verification helpers for the OIDC service.

This module deliberately isolates the small amount of cryptographic code from
the Flask web handlers in ``app.py``.

Why ``cryptography.hazmat`` is used
-----------------------------------
PyJWT can sign and verify RS256 JWTs, but it cannot generate an RSA keypair or
export the public key as a JWK. Those operations require the ``cryptography``
package. The ``hazmat`` subpackage is the public API for key generation and key
serialization in ``cryptography``; it is not the same as using the internal,
unstable pieces of the library despite the "hazmat" name.

The alternatives are:

- Shelling out to ``openssl``: adds an external process dependency and makes key
  loading/generation harder to test portably.
- Using a different RSA/JWK library: introduces another dependency even though
  ``cryptography`` is already installed and is the standard Python crypto
  backend used by PyJWT for RS256.
- Using HS256 instead of RS256: hosted OIDC clients such as Bookstack and
  NocoDB generally expect an RSA ``jwks_uri``. A symmetric key would also have
  to be shared with every client, which is less appropriate for this service.
"""

import base64
import hashlib
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SUPPORTED_SCOPES = ("openid", "profile", "email", "roles", "clearances")
JWTError = jwt.PyJWTError


def now() -> int:
    """Return the current Unix time as an integer."""
    return int(time.time())


def base64url_long(value: int) -> str:
    """Encode an integer as unpadded base64url bytes."""
    length = (value.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode()


def at_hash(token: str) -> str:
    """Return the OIDC at_hash value for an access token."""
    digest = hashlib.sha256(token.encode("utf8")).digest()
    return base64.urlsafe_b64encode(digest[:16]).rstrip(b"=").decode()


def generate_rsa_key(key_size: int = 3072):
    """Generate an RSA keypair for token signing.

    ``key_size`` defaults to 3072 bits: 2048 is still widely interoperable, but
    3072 provides a better security margin for a long-lived signing key without
    meaningful practical impact on OIDC token signing/verification.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
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


def setup_signing_keys(app, allow_ephemeral: bool = False):
    """Load or generate the RSA keypair used to sign JWTs.

    Ephemeral keys are only allowed when explicitly requested. In production,
    ``create_app`` passes ``allow_ephemeral=False`` so a missing or invalid key
    fails fast instead of silently issuing tokens signed by a key that will
    disappear on the next restart.
    """
    private_pem = app.config.get("OIDC_PRIVATE_KEY_PEM")
    if isinstance(private_pem, str):
        private_pem = private_pem.replace("\\n", "\n").encode("utf8")
    if not private_pem:
        if not allow_ephemeral:
            raise RuntimeError(
                "oidc/rsa_private_key is required in production; refusing to "
                "generate an ephemeral signing key"
            )
        private_pem, _ = generate_rsa_key()
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


def public_jwk(app):
    """Return the public JWK for the active signing key."""
    numbers = app.config["OIDC_PUBLIC_KEY_OBJ"].public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "kid": app.config["OIDC_KID"],
        "alg": "RS256",
        "n": base64url_long(numbers.n),
        "e": base64url_long(numbers.e),
    }


def sign_jwt(app, payload, ttl):
    """Create a signed RS256 JWT."""
    now_ts = now()
    token_payload = {
        **payload,
        "iss": app.config["OIDC_ISSUER"],
        "iat": now_ts,
        "exp": now_ts + ttl,
    }
    return jwt.encode(
        token_payload,
        app.config["OIDC_PRIVATE_KEY"],
        algorithm="RS256",
        headers={"kid": app.config["OIDC_KID"]},
    )


def issue_access_token(app, client_id, scopes, claims):
    """Issue an OIDC access token."""
    return sign_jwt(
        app,
        {
            "sub": claims["sub"],
            "aud": client_id,
            "scope": " ".join(scopes),
            **claims,
        },
        app.config["OIDC_ACCESS_TOKEN_TTL"],
    )


def issue_id_token(app, client_id, oidc_request, claims, access_token):
    """Issue an OIDC ID token."""
    payload = {
        "sub": claims["sub"],
        "aud": client_id,
        "auth_time": oidc_request["auth_time"],
        "at_hash": at_hash(access_token),
        **claims,
    }
    if oidc_request.get("nonce"):
        payload["nonce"] = oidc_request["nonce"]
    return sign_jwt(app, payload, app.config["OIDC_ID_TOKEN_TTL"])


def decode_access_token(app, token):
    """Decode and validate an access token JWT."""
    audiences = [c["client_id"] for c in app.config["OIDC_CLIENTS"]]
    decode_kwargs = {"algorithms": ["RS256"]}
    if audiences:
        decode_kwargs["audience"] = audiences
    return jwt.decode(
        token,
        app.config["OIDC_PUBLIC_KEY"],
        **decode_kwargs,
    )
