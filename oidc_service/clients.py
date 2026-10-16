"""OIDC client configuration helpers."""


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
