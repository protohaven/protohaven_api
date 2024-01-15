# from oauthlib.oauth2 import WebApplicationClient
import urllib.parse

import requests

from config import get_config

cfg = get_config()["neon"]
client_id = cfg["oauth_client_id"]
client_secret = cfg["oauth_client_secret"]
# client = WebApplicationClient(client_id)


def prep_request(redirect_uri):
    redirect_uri = urllib.parse.quote_plus(
        redirect_uri.replace("localhost", "127.0.0.1")
    )

    return f"https://protohaven.app.neoncrm.com/np/oauth/auth?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"


def retrieve_token(redirect_uri, authorization_code):
    rep = requests.post(
        "https://app.neoncrm.com/np/oauth/token",
        data=dict(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            code=authorization_code,
            grant_type="authorization_code",
        ),
    )
    rep.raise_for_status()
    return rep.json()


if __name__ == "__main__":
    # Note: this just proves user identity - need to track session and
    # carefully consider permissions when deciding what data to return to them.
    url = "foo.bar/asdf"
    print(prep_request(url))
    code = input("Enter your code:")
    rep = retrieve_token(url, code)
    print(rep)
