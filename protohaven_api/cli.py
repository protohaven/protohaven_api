"""A set of command line tools to be run manually or via Cronicle"""

import argparse
import logging
import sys

from protohaven_api.commands import (
    classes,
    clearances,
    comms,
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
        5.0
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


    #import re
    #from dateutil import parser as dateparser
    import json
    from protohaven_api.integrations import airtable, neon_base, neon, eventbrite
    #from protohaven_api.automation.classes import events as eauto
    from protohaven_api.integrations import models
    from protohaven_api.automation.classes import events as eauto
    from dateutil import parser as dateparser
    from protohaven_api.config import tznow
    import datetime


    #for e in eventbrite.fetch_events(status="live,started,ended,completed", batching=True):
    #     print(e)
    # now = tznow()
    # for evt in eauto.fetch_upcoming_events(merge_airtable=True):
    #     if not evt.start_date or evt.in_blocklist() or evt.end_date < now:
    #         continue
    #     print(evt.neon_id, evt.name)

    #evt_id = 18556
    #for_class = {evt_id: {k.lower(): v for k, v in airtable.get_notifications_after(re.compile(f".*{evt_id}.*"), dateparser.parse("2025-11-19")).items()}}
    #print("Class", for_class.get(evt_id))

    #email = neon_base.fetch_account(2986, required=True).email
    # print("From_email", email, for_class.get(evt_id, {}).get(email))

    #log.info(f"Looking at members...")
    #with open("/tmp/anonymized_member_start_dates.csv", 'w') as f:
    #    for mem in neon.search_all_members(fields=["First Membership Enrollment Date"]):
    #        first = None
    #        log.info(f"{mem.neon_id}")
    #        first = mem.neon_search_data.get("First Membership Enrollment Date")
    #        f.write(f"{hashlib.sha256(mem.neon_id.encode('utf8')).hexdigest()}\t{first}\n")

    #from protohaven_api.config import tznow
    #import datetime
    #from protohaven_api.integrations import booked
    # print(booked.get_reservations(tznow()-datetime.timedelta(days=14), tznow())["reservations"][0])
    #print(booked.get_user(36))

    #from protohaven_api.integrations import airtable
    # print(neon_base.get("api_key1", "accounts/1245"))
    #print(dict(airtable.fetch_instructor_teachable_classes()))

    #from dateutil import parser as dateparser
    #from protohaven_api.integrations import neon_base
    #from protohaven_api.integrations.data.neon import Category

    # print(neon_base.get("api_key1", f"/events/18477"))

    # print(neon_base.create_event(
    #         "Test event",
    #         "Please ignore",
    #         dateparser.parse("2025-11-01T18:00:00-05:00"),
    #         dateparser.parse("2025-11-01T21:00:00-05:00"),
    #         category=Category.PROJECT_BASED_WORKSHOP,
    #         max_attendees=4,
    #         dry_run=False,
    #         published=False,
    #         registration=False,
    #     ))

    # from protohaven_api.config import tznow
    # from protohaven_api.integrations import booked
    # now = tznow()
    # for res in booked.get_reservations(now.replace(hour=0, minute=0, second=0), now.replace(hour=23, minute=59, second=59))['reservations']:
    #     if res["firstName"] != "Karen":
    #         continue
    #     print(res)
