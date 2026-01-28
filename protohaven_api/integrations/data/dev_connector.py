"""Dev version of Connector class that operates on mock data"""

import logging
from json import loads
from typing import Any
from urllib.parse import urlencode, urljoin

from protohaven_api.config import get_config
from protohaven_api.integrations.data import (
    dev_booked,
    dev_discord,
    dev_eventbrite,
    dev_google,
    dev_neon,
    dev_square,
    dev_wyze,
)
from protohaven_api.integrations.data.connector import Connector

log = logging.getLogger("integrations.data.dev_connector")


class DevConnector(Connector):
    """Dev version of Connector class"""

    def __init__(self):
        Connector.__init__(self)
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
        return self._must_json(dev_neon.handle, *args, **kwargs)

    def neon_session(self):
        """Create a new session using the requests lib, or dev alternative"""
        return dev_neon.Session()

    def db_format(self):
        return "nocodb"

    def _construct_db_request_url_and_headers(  # pylint: disable=too-many-arguments
        self, base: str, tbl: str, rec: str | None, params: dict[str, Any] | None
    ):
        cfg = get_config("nocodb")
        path = f"/api/v3/data/{cfg['data'][base]['base_id']}/{cfg['data'][base][tbl]}/records"
        path += f"/{rec}" if rec else ""
        path += ("?" + urlencode(params)) if params else ""
        headers = {
            "xc-token": cfg["requests"]["token"],
            "Content-Type": "application/json",
        }
        return urljoin(cfg["requests"]["url"], path), headers

    def google_form_submit(self, url, params):
        """Submit a google form with data"""
        log.info(
            f"\n============= DEV GOOGLE FORM SUBMISSION (FAKE) ===============\n"
            f"{url}\nparams {params}\n"
            "==========================================================\n"
        )

    def discord_webhook(self, webhook, content):
        """Send content to a Discord webhook"""
        log.info(
            f"\n============= DEV DISCORD MESSAGE {webhook} (FAKE) ===============\n"
            f"{content}\n"
            "==========================================================\n"
        )
        return dev_discord.Response()

    def email(self, subject, body, recipients, _):
        """Send an email via GMail SMTP"""
        log.info(
            f"\n============= DEV EMAIL MESSAGE (FAKE) ==========\n"
            f"To: {recipients}\n"
            f"Subject: {subject}\n\n"
            f"{body}\n\n"
            "==========================================================\n"
        )

    def _discord_fn(self, fn, args, kwargs):
        if not hasattr(dev_discord, fn):
            raise NotImplementedError(f"Function {fn} not implemented in dev_discord")
        return getattr(dev_discord, fn)(*args, **kwargs)

    def discord_bot_fn(self, fn, *args, **kwargs):
        """Executes a function synchronously on the discord bot"""
        return self._discord_fn(fn, args, kwargs)

    def discord_bot_genfn(self, fn, *args, **kwargs):
        """Properly interact with a generator function in the discord bot"""
        return self._discord_fn(fn, args, kwargs)

    def discord_bot_fn_nonblocking(self, fn, *args, **kwargs):
        """Executes a function synchronously on the discord bot"""
        return self._discord_fn(fn, args, kwargs)

    def booked_request(self, *args, **kwargs):
        """Make a request to the Booked reservation system"""
        return self._must_json(dev_booked.handle, *args, **kwargs)

    def eventbrite_request(self, *args, **kwargs):
        """Make a request to the Booked reservation system"""
        return self._must_json(dev_eventbrite.handle, *args, **kwargs)

    def square_client(self):
        """Create and return Square API client"""
        return dev_square.Client()

    def asana_client(self):
        """Create and return an Asana API client"""
        raise NotImplementedError("Asana client not implemented in dev mode")

    def wyze_client(self):
        return dev_wyze.Client()

    def gcal_request(self, calendar_id, time_min, time_max):
        """Sends a calendar read request to Google Calendar"""
        return dev_google.get_calendar(calendar_id, time_min, time_max)
