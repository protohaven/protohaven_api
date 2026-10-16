# Protohaven OIDC service

This directory contains a small, standalone Flask application that acts as an
OpenID Connect (OIDC) provider for hosted Protohaven services such as Bookstack
and NocoDB.

It does not implement its own password authentication. Instead it reuses the
existing Neon CRM OAuth integration in `protohaven_api/oauth.py` and the Neon
account integration in `protohaven_api/integrations/neon_base.py`.

## How it works

1. A hosted service (OIDC client) redirects a browser to `/authorize`.
2. `/authorize` validates the OIDC client and redirects the browser to Neon
   CRM's OAuth endpoint.
3. Neon CRM returns the browser to `/callback`.
4. `/callback` exchanges the Neon code for a Neon account ID, fetches account
   data with `neon_base.fetch_account`, and redirects back to the OIDC client
   with a short-lived authorization code.
5. The OIDC client calls `/token` to exchange that code for an access token and
   signed ID token.
6. `/userinfo` returns the same identity/authorization claims for the access
   token.

## Endpoints

- `GET /.well-known/openid-configuration` - OIDC discovery document
- `GET /jwks.json` - public signing key
- `GET /authorize` - OIDC authorization endpoint
- `GET /callback` - Neon CRM OAuth callback (do not call directly)
- `POST /token` - OIDC token endpoint
- `GET /userinfo` / `POST /userinfo` - userinfo endpoint
- `GET /health` - health check

## Configuration

The service reads the repository `config.yaml` (or `$PH_CONFIG`) through the
shared `protohaven_api.config.get_config` helper. The following `oidc` section
values are used:

| Key | Purpose |
| --- | --- |
| `oidc/issuer` | Public base URL for this service, e.g. `https://oidc.protohaven.org` |
| `oidc/session_secret` | Flask session signing secret. Required in production; dev/test may use an ephemeral key. |
| `oidc/rsa_private_key` | PEM RSA private key used to sign JWTs. Required in production; dev/test may use an ephemeral key. |
| `oidc/access_token_ttl_sec` | Access token lifetime (default 3600) |
| `oidc/id_token_ttl_sec` | ID token lifetime (default 3600) |
| `oidc/auth_code_ttl_sec` | Authorization code lifetime (default 600) |
| `oidc/authorize_rate_limit_per_min` | Allowed `/authorize` requests per IP per minute (default 60) |
| `oidc/token_rate_limit_per_min` | Allowed `/token` requests per IP per minute (default 30) |
| `oidc/auth_failure_lockout_threshold` | Failed auth attempts before a temporary lockout (default 10) |
| `oidc/auth_failure_lockout_sec` | Lockout duration in seconds (default 900) |
| `oidc/clients` | List of OIDC clients with `client_id`, `client_secret`, and `redirect_uris` |

For production, set `OIDC_ISSUER` to the externally reachable URL and configure
a persistent `OIDC_RSA_PRIVATE_KEY` (use `\n` for line breaks in env files) and
`OIDC_SESSION_SECRET`.

Neon OAuth credentials and Neon API keys come from the existing `neon` section.
The Neon OAuth client must have `{issuer}/callback` registered as a redirect
URI.

## Running locally

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# Use 127.0.0.1 rather than localhost because the shared Neon OAuth helper
# rewrites localhost to 127.0.0.1, which can otherwise break the Flask session
# cookie on the return redirect.
export OIDC_ISSUER=http://127.0.0.1:5002
venv/bin/python -m oidc_service.main
```

Then configure a test OIDC client in `config.yaml` (or environment overrides)
and point it at `http://127.0.0.1:5002/.well-known/openid-configuration`.

## Operational notes

Authorization codes are encrypted and short-lived, and they are single-use.
Replay protection uses in-process storage with TTL cleanup. Rate limiting and
failed-auth lockouts are also process-local, so this service is designed for a
single OIDC worker. Replace the in-process stores with a shared store before
running multiple workers.

In production the service refuses to start without both `oidc/session_secret`
and `oidc/rsa_private_key`. It also enables `Secure` session cookies when
`oidc/issuer` is HTTPS.

## Tokens and claims

Tokens are signed RS256 JWTs. The service always includes the following claims
for authorization purposes:

- `sub` / `neon_id` - Neon account ID
- `roles` - Neon "API server role" custom field values
- `clearances` - Neon "Clearances" custom field values
- `member` - whether the Neon account currently has Active membership

`name` and `preferred_username` are included when the client requests the
`profile` scope. `email` is included when the client requests the `email` scope.
