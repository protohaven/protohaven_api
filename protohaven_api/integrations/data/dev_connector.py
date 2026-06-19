"""Dev version of Connector class that operates on mock data"""

import logging
from json import loads

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

    def cache_server_request(self, endpoint: str, params: dict) -> dict:
        """Dev mode: query the local AccountCache directly instead of making HTTP calls."""
        # Lazy import to avoid circular dependency at module load time
        from protohaven_api.integrations import neon  # pylint: disable=import-outside-toplevel

        if endpoint == "/find_best_match":
            search: str = params.get("search", "")
            top_n: int = int(params.get("top_n", 10))
            score_cutoff: int = int(params.get("score_cutoff", 65))
            results: list[dict] = []
            for member in neon.cache.find_best_match(
                search, top_n=top_n, score_cutoff=score_cutoff
            ):
                results.append({
                    "neon_raw_data": member.neon_raw_data,
                    "neon_search_data": member.neon_search_data,
                    "neon_membership_data": member.neon_membership_data,
                    "airtable_bio_data": member.airtable_bio_data,
                })
            return results

        if endpoint == "/get":
            key: str = params.get("key", "")
            if not key:
                return {"error": "key parameter is required"}
            fetch_if_missing: bool = str(params.get("fetch_if_missing", "1")) != "0"
            data = neon.cache.get(key, {}, fetch_if_missing=fetch_if_missing)
            result: dict = {}
            for neon_id, member in data.items():
                result[neon_id] = {
                    "neon_raw_data": member.neon_raw_data,
                    "neon_search_data": member.neon_search_data,
                    "neon_membership_data": member.neon_membership_data,
                    "airtable_bio_data": member.airtable_bio_data,
                }
            return result

        raise ValueError(f"Unknown cache server endpoint: {endpoint}")
