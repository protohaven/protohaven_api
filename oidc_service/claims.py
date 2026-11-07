"""Neon account and OIDC claim helpers."""

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


def userinfo_claims(payload):
    """Return only the user-identity claims from a JWT payload."""
    allowed = set(USERINFO_CLAIM_NAMES)
    return {k: payload[k] for k in allowed if k in payload}
