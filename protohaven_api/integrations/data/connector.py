""" Connects to various dependencies, or serves mock data depending on the
configured state of the server"""
import base64
import logging
import random
import time
from email.mime.text import MIMEText
from threading import Lock

import asana
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from square.client import Client as SquareClient

from protohaven_api.config import get_config
from protohaven_api.integrations import discord_bot

log = logging.getLogger("integrations.data.connector")

DEFAULT_TIMEOUT = 20.0
NUM_READ_ATTEMPTS = 3
RETRY_MAX_DELAY_SEC = 3.0

AIRTABLE_URL = "https://api.airtable.com/v0"


class Connector:
    """Provides production access to dependencies."""

    def __init__(self):
        self.neon_ratelimit = Lock()

    def neon_request(self, api_key, *args, **kwargs):
        """Make a neon request"""
        auth = (get_config("neon/domain"), api_key)
        # log.info(f"{auth} {args} {kwargs}")

        # Attendee endpoint is often called repeatedly; runs into
        # neon request ratelimit. Here we globally synchronize and
        # include a sleep timer to prevent us from overrunning
        if "/attendees" in args[0]:
            with self.neon_ratelimit:
                r = requests.request(
                    *args, **kwargs, auth=auth, timeout=DEFAULT_TIMEOUT
                )
                time.sleep(0.25)
        else:
            r = requests.request(*args, **kwargs, auth=auth, timeout=DEFAULT_TIMEOUT)

        if r.status_code != 200:
            raise RuntimeError(
                f"neon_request(args={args}, kwargs={kwargs}) returned {r.status_code}: {r.content}"
            )
        try:
            return r.json()
        except requests.exceptions.JSONDecodeError:
            return r.content

    def neon_session(self):
        """Create a new session using the requests lib"""
        return requests.Session()

    def _handle_airtable_request(self, mode, url, data, token):
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        rep = requests.request(
            mode, url, headers=headers, timeout=DEFAULT_TIMEOUT, data=data
        )
        return rep.status_code, rep.content

    def airtable_request(
        self, mode, base, tbl, rec=None, suffix=None, data=None
    ):  # pylint: disable=too-many-arguments
        """Make an airtable request using the requests module"""
        cfg = get_config("airtable")[base]
        url = f"{AIRTABLE_URL}/{cfg['base_id']}/{cfg[tbl]}"
        if rec:
            url += f"/{rec}"
        if suffix:
            url += suffix
        for i in range(NUM_READ_ATTEMPTS):
            try:
                return self._handle_airtable_request(mode, url, data, cfg["token"])
            except requests.exceptions.ReadTimeout as rt:
                if mode != "GET" or i == NUM_READ_ATTEMPTS - 1:
                    raise rt
                log.warning(
                    f"ReadTimeout on airtable request {mode} {base} {tbl} "
                    f"{rec} {suffix}, retry #{i+1}"
                )
                time.sleep(int(random.random() * RETRY_MAX_DELAY_SEC))
        return None, None

    def google_form_submit(self, url, params):
        """Submit a google form with data"""
        return requests.get(url, params, timeout=DEFAULT_TIMEOUT)

    def discord_webhook(self, webhook, content):
        """Send content to a Discord webhook"""
        return requests.post(
            webhook, json={"content": content}, timeout=DEFAULT_TIMEOUT
        )

    def email(self, subject: str, body: str, recipients: list, html: bool):
        """Send an email via GMail SMTP.
        Service account is granted domain-wide delegation with this scope, so it's
        able to send emails as anyone with an @protohaven.org suffix.

        Delegation setting:
        https://admin.google.com/ac/owl/domainwidedelegation

        Service account:
        https://console.cloud.google.com/iam-admin/serviceaccounts/details/116847738113181289731
        (workshop@ user is service account admin)

        Docs:
        https://developers.google.com/identity/protocols/oauth2/service-account#delegatingauthority
        """
        try:
            from_addr = get_config("comms/email_username")
            creds = service_account.Credentials.from_service_account_file(
                get_config("gmail/credentials_path"), scopes=get_config("gmail/scopes")
            ).with_subject(from_addr)
            service = build("gmail", "v1", credentials=creds)
            msg = MIMEText(body, "html" if html else "plain")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = ", ".join(recipients)
            result = (
                service.users()  # pylint: disable=no-member
                .messages()
                .send(
                    userId=from_addr,
                    body={"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()},
                )
                .execute()
            )
            return result
        except HttpError as e:
            log.error(f"Failed to send email to {recipients}: {e}")
            return None

    def discord_bot_fn(self, fn, *args, **kwargs):
        """Executes a function synchronously on the discord bot"""
        return discord_bot.invoke_sync(fn, *args, **kwargs)

    def discord_bot_genfn(self, fn, *args, **kwargs):
        """Properly interact with a generator function in the discord bot"""
        return discord_bot.invoke_sync_generator(fn, *args, **kwargs)

    def discord_bot_fn_nonblocking(self, fn, *args, **kwargs):
        """Executes a function synchronously on the discord bot"""
        return getattr(discord_bot.get_client(), fn)(*args, **kwargs)

    def booked_request(self, *args, **kwargs):
        """Make a request to the Booked reservation system"""
        headers = {
            "X-Booked-ApiId": get_config("booked/id"),
            "X-Booked-ApiKey": get_config("booked/key"),
        }
        return requests.request(
            *args, headers=headers, timeout=DEFAULT_TIMEOUT, **kwargs
        )

    def square_client(self):
        """Create and return Square API client"""
        client = SquareClient(
            access_token=get_config("square/token"),
            environment="production",
        )
        return client

    def asana_client(self):
        """Create and return an Asana API client"""
        acfg = asana.Configuration()
        acfg.access_token = get_config("asana/token")
        client = asana.ApiClient(acfg)
        client.default_headers["asana-enable"] = "new_goal_memberships"
        return client

    def asana_tasks(self):
        """Create and return asana TasksApi"""
        return asana.TasksApi(self.asana_client())

    def asana_projects(self):
        """Create and return asana ProjectsApi"""
        return asana.ProjectsApi(self.asana_client())

    def asana_sections(self):
        """Create and return asana SectionsApi"""
        return asana.SectionsApi(self.asana_client())


C = None


def init(cls):
    """Initialize the connector"""
    global C  # pylint: disable=global-statement
    C = cls()


def get():
    """Get the initialized connector, or None if not initialized"""
    return C
