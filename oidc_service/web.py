"""Flask request/response helpers for the OIDC handlers."""

from urllib.parse import urlencode

from flask import jsonify, redirect, request


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


def client_credentials():
    """Read client credentials from HTTP Basic or the token request body."""
    if request.authorization and request.authorization.type == "basic":
        return request.authorization.username, request.authorization.password or ""
    return request.form.get("client_id", ""), request.form.get("client_secret", "")


def url_with_params(base, params):
    """Append query parameters to a URL."""
    return f"{base}?{urlencode(params)}"


def state_params(state):
    """Return a one-item dict for state when it is present."""
    return {} if state is None else {"state": state}
