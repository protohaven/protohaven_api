"""OAuth integration with Neon CRM"""

import urllib.parse

import requests

from protohaven_api.config import get_config


def client_data():
    """Fetch client data for oauth"""
    cfg = get_config()["neon"]
    client_id = cfg["oauth_client_id"]
    client_secret = cfg["oauth_client_secret"]
    return client_id, client_secret


def prep_request(redirect_uri):
    """Prepare an oauth URI"""
    redirect_uri = urllib.parse.quote_plus(
        redirect_uri.replace("localhost", "127.0.0.1")
    )
    client_id = client_data()
    return (
        "https://protohaven.app.neoncrm.com/np/oauth/auth?"
        + f"response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"
    )


def retrieve_token(redirect_uri, authorization_code):
    """Get the user token (i.e. the user's account_id) after a successful OAuth"""
    client_id, client_secret = client_data()
    rep = requests.post(
        "https://app.neoncrm.com/np/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": authorization_code,
            "grant_type": "authorization_code",
        },
        timeout=5.0,
    )
    rep.raise_for_status()
    return rep.json()


if __name__ == "__main__":
    # Note: this just proves user identity - need to track session and
    # carefully consider permissions when deciding what data to return to them.
    URL = "foo.bar/asdf"
    print(prep_request(URL))
    code = input("Enter your code:")
    tkn = retrieve_token(URL, code)
    print(tkn)
