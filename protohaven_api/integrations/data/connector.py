""" Connects to various dependencies, or serves mock data depending on the
configured state of the server"""
import asyncio
import json
import logging
import random
import smtplib
import time
from email.mime.text import MIMEText
from threading import Lock

import asana
import httplib2
import requests
from square.client import Client as SquareClient

from protohaven_api.config import get_config
from protohaven_api.discord_bot import get_client as get_discord_bot
from protohaven_api.integrations.data import dev_airtable, dev_neon
from protohaven_api.integrations.data.loader import (  # pylint: disable=unused-import
    mock_data,
)

log = logging.getLogger("integrations.data.connector")

DEFAULT_TIMEOUT = 5.0
NUM_READ_ATTEMPTS = 3
RETRY_MAX_DELAY_SEC = 3.0


AIRTABLE_URL = "https://api.airtable.com/v0"


class DevDiscordResponse:  # pylint: disable=too-few-public-methods
    """Discord response in dev mode"""

    def raise_for_status(self):
        """Do nothing; stub only"""


class Connector:
    """Provides dev and production access to dependencies.
    In the case of dev, mock data and sandboxes are used to
    fulfill requests and method calls."""

    def __init__(self, dev):
        self.dev = dev
        self.cfg = get_config()
        self.neon_ratelimit = Lock()

    def neon_request(self, api_key, *args, **kwargs):
        """Make a neon request, passing through to httplib2"""
        if self.dev:
            resp = dev_neon.handle(*args, **kwargs)
            status = resp.status_code
            content = resp.data
        else:
            h = httplib2.Http(".cache")
            h.add_credentials(self.cfg["neon"]["domain"], api_key)

            # Attendee endpoint is often called repeatedly; runs into
            # neon request ratelimit. Here we globally synchronize and
            # include a sleep timer to prevent us from overrunning
            if "/attendees" in args[0]:
                with self.neon_ratelimit:
                    resp, content = h.request(*args, **kwargs)
                    time.sleep(0.25)
            else:
                resp, content = h.request(*args, **kwargs)
            status = resp.status

        if status != 200:
            raise RuntimeError(
                f"neon_request(args={args}, kwargs={kwargs}) returned {status}: {content}"
            )
        return json.loads(content)

    def _neon_session_dev(self):
        """Dev handler for neon session creation"""
        raise NotImplementedError(
            "Neon session creation not implemented for dev environment"
        )

    def neon_session(self):
        """Create a new session using the requests lib, or dev alternative"""
        if self.dev:
            return self._neon_session_dev()
        return requests.Session()

    def airtable_request(
        self, mode, base, tbl, rec=None, suffix=None, data=None
    ):  # pylint: disable=too-many-arguments
        """Make an airtable request using the requests module"""
        cfg = self.cfg["airtable"][base]
        headers = {
            "Authorization": f"Bearer {cfg['token']}",
            "Content-Type": "application/json",
        }
        url = f"{AIRTABLE_URL}/{cfg['base_id']}/{cfg[tbl]}"
        if rec:
            url += f"/{rec}"
        if suffix:
            url += suffix
        for i in range(NUM_READ_ATTEMPTS):
            try:
                if self.dev:
                    rep = dev_airtable.handle(mode, url, data)
                    return rep.status_code, rep.data

                rep = requests.request(
                    mode, url, headers=headers, timeout=DEFAULT_TIMEOUT, data=data
                )
                return rep.status_code, rep.content
            except requests.exceptions.ReadTimeout as rt:
                if mode != "GET" or i == NUM_READ_ATTEMPTS - 1:
                    raise rt
                log.warning(
                    f"ReadTimeout on airtable request {mode} {base} {tbl} "
                    f"{rec} {suffix}, retry #{i+1}"
                )
                time.sleep(int(random.random() * RETRY_MAX_DELAY_SEC))
        return None, None

    def _google_form_submit_dev(self, url, params):
        """Dev handler for submitting google forms"""
        log.info(f"Suppressing google form submission: {url}, params {params}")

    def google_form_submit(self, url, params):
        """Submit a google form with data"""
        if self.dev:
            return self._google_form_submit_dev(url, params)
        return requests.get(url, params, timeout=DEFAULT_TIMEOUT)

    def _discord_webhook_dev(self, webhook, content):
        """Dev handler for discord webhooks"""
        log.info(
            f"Suppressing Discord webhook submission: {webhook}, content {content}"
        )
        return DevDiscordResponse()

    def discord_webhook(self, webhook, content):
        """Send content to a Discord webhook"""
        if self.dev:
            return self._discord_webhook_dev(webhook, content)
        return requests.post(
            webhook, json={"content": content}, timeout=DEFAULT_TIMEOUT
        )

    def _email_dev(self, subject, body, recipients):
        """Dev handler for email sending"""
        log.info(
            f"Suppressing email sending to {recipients}:\nSubject: {subject}\n{body}"
        )

    def email(self, subject, body, recipients):
        """Send an email via GMail SMTP"""
        if self.dev:
            return self._email_dev(subject, body, recipients)
        sender = self.cfg["comms"]["email_username"]
        passwd = self.cfg["comms"]["email_password"]
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
            smtp_server.login(sender, passwd)
            smtp_server.sendmail(sender, recipients, msg.as_string())
        return None

    def _discord_bot_setnick_dev(self, name, nick):
        """Dev handler for setting a nickname"""
        raise NotImplementedError("TODO")

    def discord_bot_setnick(self, name, nick):
        """Sets the nickname of a user on Discord"""
        if self.dev:
            return self._discord_bot_setnick_dev(name, nick)
        client = get_discord_bot()
        result = asyncio.run_coroutine_threadsafe(
            client.set_nickname(name, nick), client.loop
        ).result()
        return result

    def _discord_bot_setrole_dev(self, name, role):
        """Dev handler for setting a discord role"""
        raise NotImplementedError("TODO")

    def discord_bot_setrole(self, name, role):
        """Set the role of a server member on Discord"""
        if self.dev:
            return self._discord_bot_setrole_dev(name, role)
        client = get_discord_bot()
        result = asyncio.run_coroutine_threadsafe(
            client.grant_role(name, role), client.loop
        ).result()
        return result

    def discord_bot_revoke_role(self, name, role):
        """Set the role of a server member on Discord"""
        if self.dev:
            return self._discord_bot_setrole_dev(name, role)
        client = get_discord_bot()
        result = asyncio.run_coroutine_threadsafe(
            client.revoke_role(name, role), client.loop
        ).result()
        return result

    def _discord_bot_get_all_members_and_roles_dev(self):
        raise NotImplementedError("TODO")

    def discord_bot_get_all_members_and_roles(self):
        """Fetch all members and roles on Discord"""
        if self.dev:
            return self._discord_bot_get_all_members_and_roles_dev()
        client = get_discord_bot()
        result = asyncio.run_coroutine_threadsafe(
            client.get_all_members_and_roles(), client.loop
        ).result()
        return result

    def _discord_bot_send_dm(self, user, msg):
        raise NotImplementedError("TODO")

    def discord_bot_send_dm(self, user, msg, blocking=True):
        """Sends a DM to a specific user"""
        if self.dev:
            return self._discord_bot_send_dm(user, msg)
        client = get_discord_bot()

        if blocking:
            result = asyncio.run_coroutine_threadsafe(
                client.send_dm(user, msg), client.loop
            ).result()
        else:
            result = client.send_dm(user, msg)
        return result

    def _booked_request_dev(self, *args, **kwargs):
        """Dev handler for reservation system requests"""
        raise NotImplementedError("TODO")

    def booked_request(self, *args, **kwargs):
        """Make a request to the Booked reservation system"""
        if self.dev:
            return self._booked_request_dev(*args, **kwargs)
        headers = {
            "X-Booked-ApiId": self.cfg["booked"]["id"],
            "X-Booked-ApiKey": self.cfg["booked"]["key"],
        }
        return requests.request(
            *args, headers=headers, timeout=DEFAULT_TIMEOUT, **kwargs
        )

    def square_client(self):
        """Create and return Square API client"""
        client = SquareClient(
            access_token=self.cfg["square"]["token"],
            environment="production" if not self.dev else "sandbox",
        )
        return client

    def _asana_client_dev(self):
        """Dev handler for asana client creation"""
        raise NotImplementedError("TODO")

    def asana_client(self):
        """Create and return an Asana API client"""
        if self.dev:
            return self._asana_client_dev()
        acfg = asana.Configuration()
        acfg.access_token = self.cfg["asana"]["token"]
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


def init(dev):
    """Initialize the connector"""
    global C  # pylint: disable=global-statement
    C = Connector(dev)


def get():
    """Get the initialized connector, or None if not initialized"""
    return C
