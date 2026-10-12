"""Commands for backing up and inspecting Cronicle configuration."""

import argparse
import logging
import tempfile
from pathlib import Path

from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import get_config, tznow
from protohaven_api.integrations import drive
from protohaven_api.integrations.comms import Msg
from protohaven_api.integrations.cronicle import CronicleClient, schedule_backup

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
        arg(
            "--parent_id",
            help="destination folder ID",
            type=str,
            required=True,
        ),
        arg(
            "--apply",
            help="actually create the backup",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
    )
    def backup_cronicle(self, args, _):
        """Fetch and back up Cronicle event definitions to Google Drive."""
        base_url = (
            args.base_url
            or get_config("cronicle/base_url")
            or "https://cron.protohaven.org"
        )
        now = tznow()

        # Note: dest drive must be shared with protohaven-cli@protohaven-api.iam.gserviceaccount.com
        client = CronicleClient(base_url, args.api_key)
        with tempfile.TemporaryDirectory() as d:
            backup_path = Path(d) / "cronicle_backup.tar.gz"
            file_sz = schedule_backup(client, str(backup_path))
            upload_path = f"cronicle_backup_{now.isoformat()}.tar.gz"
            log.info(f"Fetched {backup_path}; pushing to drive as {upload_path}")
            if args.apply:
                file_id = drive.upload_file(
                    str(backup_path),
                    "application/x-gzip-compressed",
                    upload_path,
                    args.parent_id,
                )
                log.info(f"Uploaded, id {file_id}")
            else:
                file_id = "DRY_RUN"
                file_sz = 0
            stats = [
                {
                    "drive_id": file_id,
                    "size_kb": file_sz // 1024,
                    "name": upload_path,
                }
            ]

        print_yaml(
            Msg.tmpl(
                "cronicle_backup_summary",
                parent_id=args.parent_id,
                stats=stats,
                target="#cronicle-automation",
            )
        )
        log.info("Done")
