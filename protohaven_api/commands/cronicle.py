"""Commands for backing up and inspecting Cronicle configuration."""

import json
import logging

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import get_config
from protohaven_api.qa.cronicle import CronicleClient

log = logging.getLogger("cli.cronicle")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for Cronicle configuration backups."""

    @command(
        arg(
            "--base_url",
            help="Base URL for the Cronicle server",
            type=str,
            default=None,
        ),
        arg(
            "--api_key",
            help="Cronicle API key",
            type=str,
            required=True,
        ),
    )
    def backup_cronicle(self, args, _):
        """Back up all Cronicle event definitions as multijson.

        One JSON object is emitted per line so the output can be redirected
        to a ``*.multijson`` file.
        """
        base_url = (
            args.base_url
            or get_config("cronicle/base_url")
            or "https://cron.protohaven.org"
        )
        log.info(f"Backing up Cronicle schedule from {base_url}")
        client = CronicleClient(base_url, args.api_key)
        schedule = client.schedule()
        rows = schedule.get("rows", []) if isinstance(schedule, dict) else []
        for row in rows:
            print(json.dumps(row, sort_keys=True, default=str))
        log.info(f"Backed up {len(rows)} Cronicle event definitions")
