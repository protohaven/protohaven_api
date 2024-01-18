""" Connects to various dependencies, or serves mock data depending on the
configured state of the server"""
import asyncio
import json
import smtplib
from email.mime.text import MIMEText

import httplib2
import requests
from asana import Client as AsanaClient
from square.client import Client as SquareClient

from protohaven_api.config import get_config
from protohaven_api.discord_bot import get_client as get_discord_bot

cfg = get_config()


class Connector:
    """Provides dev and production access to dependencies.
    In the case of dev, mock data and sandboxes are used to
    fulfill requests and method calls."""

    def __init__(self, dev):
        self.dev = dev
        self.data = None
        if dev:
            with open("mock_data.json", "r", encoding="utf-8") as f:
                self.data = json.loads(f.read())
            print("Mock data loaded")

    def _neon_request_dev(self, *args, **kwargs):
        """Dev handler for neon requests"""
        raise NotImplementedError("TODO")

    def neon_request(self, api_key, *args, **kwargs):
        """Make a neon request, passing through to httplib2"""
        if self.dev:
            return self._neon_request_dev(*args, **kwargs)
        h = httplib2.Http(".cache")
        h.add_credentials(cfg["neon"]["domain"], api_key)
        return h.request(*args, **kwargs)

    def _neon_session_dev(self):
        """Dev handler for neon session creation"""
        raise NotImplementedError("TODO")

    def neon_session(self):
        """Create a new session using the requests lib, or dev alternative"""
        if self.dev:
            return self._neon_session_dev()
        return requests.Session()

    def _airtable_request_dev(self, *args, **kwargs):
        """Dev handler for airtable web requests"""
        raise NotImplementedError("TODO")

    def airtable_request(self, token, *args, **kwargs):
        """Make an airtable request using the requests module"""
        if self.dev:
            return self._airtable_request_dev(*args, **kwargs)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        return requests.request(*args, headers=headers, timeout=5.0, **kwargs)

    def _discord_webhook_dev(self, webhook, content):
        """Dev handler for discord webhooks"""
        raise NotImplementedError("TODO")

    def discord_webhook(self, webhook, content):
        """Send content to a Discord webhook"""
        if self.dev:
            return self._discord_webhook_dev(webhook, content)
        return requests.post(webhook, json={"content": content}, timeout=5.0)

    def _email_dev(self, subject, body, recipients):
        """Dev handler for email sending"""
        raise NotImplementedError("TODO")

    def email(self, subject, body, recipients):
        """Send an email via GMail SMTP"""
        if self.dev:
            return self._email_dev(subject, body, recipients)
        sender = cfg["comms"]["email_username"]
        passwd = cfg["comms"]["email_password"]
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
            client.grant_role(name, "Members"), client.loop
        ).result()
        return result

    def _booked_request_dev(self, *args, **kwargs):
        """Dev handler for reservation system requests"""
        raise NotImplementedError("TODO")

    def booked_request(self, *args, **kwargs):
        """Make a request to the Booked reservation system"""
        if self.dev:
            return self._booked_request_dev(*args, **kwargs)
        headers = {
            "X-Booked-ApiId": cfg["booked"]["id"],
            "X-Booked-ApiKey": cfg["booked"]["key"],
        }
        return requests.request(*args, headers=headers, timeout=5.0, **kwargs)

    def square_client(self):
        """Create and return Square API client"""
        client = SquareClient(
            access_token=cfg["square"]["token"],
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
        client = AsanaClient.access_token(cfg["asana"]["token"])
        return client


C = None


def init(dev):
    """Initialize the connector"""
    global C  # pylint: disable=global-statement
    C = Connector(dev)


def get():
    """Get the initialized connector, or None if not initialized"""
    return C
