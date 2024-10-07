"""Dev version of Connector class that operates on mock data"""
import json
import logging

from protohaven_api.integrations.data import dev_airtable, dev_neon
from protohaven_api.integrations.data.connector import Connector

log = logging.getLogger("integrations.data.dev_connector")


class DevDiscordResponse:  # pylint: disable=too-few-public-methods
    """Discord response in dev mode"""

    def raise_for_status(self):
        """Do nothing; stub only"""


class DevConnector(Connector):
    """Dev version of Connector class"""

    def __init__(self):
        Connector.__init__(self)
        self.mutated = False
        self.sent_comms = False
        log.warning("DevConnector in use; mutations will not reach production")

    def neon_request(self, _, *args, **kwargs):
        """Make a neon request, passing through to httplib2"""
        if len(args) > 1 and args[2] != "GET":
            self.mutated = True
        resp = dev_neon.handle(*args, **kwargs)
        status = resp.status_code
        content = resp.data
        if status != 200:
            raise RuntimeError(
                f"neon_request(args={args}, kwargs={kwargs}) returned {status}: {content}"
            )
        return json.loads(content)

    def neon_session(self):
        """Create a new session using the requests lib, or dev alternative"""
        raise NotImplementedError(
            "Neon session creation not implemented for dev environment"
        )

    def _handle_airtable_request(self, mode, url, data, _):
        rep = dev_airtable.handle(mode, url, data)
        if mode != "GET":
            self.mutated = True
        return rep.status_code, rep.data

    def google_form_submit(self, url, params):
        """Submit a google form with data"""
        log.info(f"Suppressing google form submission: {url}, params {params}")
        self.mutated = True

    def discord_webhook(self, webhook, content):
        """Send content to a Discord webhook"""
        log.info(
            f"Suppressing Discord webhook submission: {webhook}, content {content}"
        )
        self.sent_comms = True
        return DevDiscordResponse()

    def email(self, subject, body, recipients, _):
        """Send an email via GMail SMTP"""
        log.info(
            f"Suppressing email sending to {recipients}:\nSubject: {subject}\n{body}"
        )
        self.sent_comms = True

    def discord_bot_fn(self, fn, *args, **kwargs):
        """Executes a function synchronously on the discord bot"""
        raise NotImplementedError("TODO")

    def discord_bot_genfn(self, fn, *args, **kwargs):
        """Properly interact with a generator function in the discord bot"""
        raise NotImplementedError("TODO")

    def discord_bot_fn_nonblocking(self, fn, *args, **kwargs):
        """Executes a function synchronously on the discord bot"""
        raise NotImplementedError("TODO")

    def booked_request(self, *args, **kwargs):
        """Make a request to the Booked reservation system"""
        raise NotImplementedError("TODO")

    def square_client(self):
        """Create and return Square API client"""
        raise NotImplementedError("TODO")

    def asana_client(self):
        """Create and return an Asana API client"""
        raise NotImplementedError("TODO")
