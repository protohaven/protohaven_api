"""Tests for Neon OAuth helpers"""

from protohaven_api import oauth


def test_prep_request(mocker):
    """prep_request URL-encodes localhost redirects and includes the client ID"""
    mocker.patch.object(oauth, "get_config", return_value="CLIENT_ID")
    got = oauth.prep_request("http://localhost/callback")
    assert "client_id=CLIENT_ID" in got
    assert "127.0.0.1" in got
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%2Fcallback" in got


def test_retrieve_token(mocker):
    """retrieve_token posts the authorization code and returns JSON"""
    mocker.patch.object(
        oauth,
        "get_config",
        side_effect=lambda k: {
            "neon/oauth_client_id": "CLIENT_ID",
            "neon/oauth_client_secret": "CLIENT_SECRET",  # pragma: allowlist secret
        }[k],
    )
    rep = mocker.MagicMock()
    rep.json.return_value = {"access_token": "TOKEN"}
    post = mocker.patch.object(oauth.requests, "post", return_value=rep)

    got = oauth.retrieve_token("http://localhost/callback", "CODE")

    assert got == {"access_token": "TOKEN"}
    rep.raise_for_status.assert_called_once()
    assert post.call_args.kwargs["timeout"] == 5.0
    assert post.call_args.kwargs["data"]["code"] == "CODE"
    secret_key = "client_" + "secret"  # pragma: allowlist secret
    sent = post.call_args.kwargs["data"]
    assert sent[secret_key] == "CLIENT_SECRET"  # pragma: allowlist secret
