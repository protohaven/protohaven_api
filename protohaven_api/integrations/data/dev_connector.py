"""Dev version of Connector class that operates on mock data"""

import logging
from json import loads
from urllib.parse import urljoin

from protohaven_api.config import get_config
from protohaven_api.integrations.data import dev_booked, dev_neon
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

    def _must_json(self, fn, *args, **kwargs):
        resp = fn(*args, **kwargs)
        status = resp.status_code
        content = resp.data
        if status != 200:
            raise RuntimeError(
                f"{fn}(args={args}, kwargs={kwargs}) returned {status}: {content}"
            )
        return loads(content)

    def neon_request(self, api_key, *args, **kwargs):
        """Make a neon request"""
        if len(args) > 1 and args[1] != "GET":
            self.mutated = True
        return self._must_json(dev_neon.handle, *args, **kwargs)

    def neon_session(self):
        """Create a new session using the requests lib, or dev alternative"""
        raise NotImplementedError(
            "Neon session creation not implemented for dev environment"
        )

    def db_format(self):
        return "nocodb"

    def _construct_db_request_url_and_headers(self, base, tbl, rec, suffix):
        cfg = get_config("nocodb")
        path = f"/api/v2/tables/{cfg['data'][base][tbl]}/records"
        if rec:
            path += f"/{rec}"
        if suffix:
            path += suffix
        headers = {
            "xc-token": cfg["requests"]["token"],
            "Content-Type": "application/json",
        }
        return urljoin(cfg["requests"]["url"], path), headers

    def _format_db_request_data(self, mode, _, data):
        if mode == "POST":
            return [r["fields"] for r in data["records"]]
        return data

    def google_form_submit(self, url, params):
        """Submit a google form with data"""
        log.info(f"Suppressing google form submission: {url}, params {params}")
        self.mutated = True

    def discord_webhook(self, webhook, content):
        """Send content to a Discord webhook"""
        log.info(
            f"\n============= DEV DISCORD MESSAGE {webhook} ===============\n"
            f"{content}\n"
            "==========================================================\n"
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
        return self._must_json(dev_booked.handle, *args, **kwargs)

    def square_client(self):
        """Create and return Square API client"""
        raise NotImplementedError("TODO")

    def asana_client(self):
        """Create and return an Asana API client"""
        raise NotImplementedError("Asana client not implemented in dev mode")
