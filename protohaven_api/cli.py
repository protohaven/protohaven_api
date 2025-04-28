""" A set of command line tools to be run manually or via Cronicle"""

import argparse
import logging
import sys

from protohaven_api.commands import (
    classes,
    clearances,
    comms,
    docs,
    finances,
    forwarding,
    maintenance,
    reservations,
    roles,
    violations,
)
from protohaven_api.config import get_config
from protohaven_api.integrations.cronicle import Progress
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.integrations.data.dev_connector import DevConnector

logging.basicConfig(level=get_config("general/log_level").upper())
log = logging.getLogger("cli")
server_mode = get_config("general/server_mode").lower()
log.info(f"Mode is {server_mode}\n")
init_connector(Connector if server_mode == "prod" else DevConnector)

if get_config("discord_bot/enabled", as_bool=True):
    import threading
    import time

    from protohaven_api.integrations.discord_bot import run as run_bot

    threading.Thread(target=run_bot, daemon=True).start()
    time.sleep(
        2.0
    )  # Hacky - should use `wait_until_ready` but there's threading problems
else:
    log.debug("Skipping startup of discord bot")


class ProtohavenCLI(  # pylint: disable=too-many-ancestors
    comms.Commands,
    reservations.Commands,
    classes.Commands,
    forwarding.Commands,
    finances.Commands,
    violations.Commands,
    roles.Commands,
    maintenance.Commands,
    docs.Commands,
    clearances.Commands,
):
    """argparser-based CLI for protohaven operations"""

    def __init__(self, args=sys.argv[1:2]):
        def fmt_usage():
            return "\n".join(
                [
                    f"{a}: {getattr(self, a).__doc__}"
                    for a in dir(self)
                    if not a.startswith("_")
                ]
            )

        parser = argparse.ArgumentParser(
            description="Protohaven CLI",
        )
        parser.format_usage = fmt_usage
        parser.add_argument("command", help="Subcommand to run")
        args = parser.parse_args(sys.argv[1:2])  # Limit to only initial command args
        if not hasattr(self, args.command):
            parser.print_help()
            sys.exit(1)
        getattr(self, args.command)(
            sys.argv[2:], Progress()
        )  # Ignore first two argvs - already parsed


if __name__ == "__main__":
    ProtohavenCLI()
