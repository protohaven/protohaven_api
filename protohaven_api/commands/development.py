"""Commands related to developing on the API"""
import logging
import pickle
from collections import defaultdict

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import get_config  # pylint: disable=import-error
from protohaven_api.integrations import airtable, neon  # pylint: disable=import-error

log = logging.getLogger("cli.dev")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for development"""

    @command(
        arg("--path", help="Path to destination file", type=str, required=True),
    )
    def gen_mock_data(self, args):
        """Fetch mock data from airtable, neon etc.
        Write this to a file for running without touching production data"""
        log.info("Fetching events from neon...")
        events = neon.fetch_events()
        # Could also fetch attendees here if needed
        log.info("Fetching clearance codes from neon...")
        clearance_codes = neon.fetch_clearance_codes()

        log.info("Fetching accounts from neon...")
        accounts = []
        for acct_id in [1797, 1727, 1438, 1355]:
            accounts.append(neon.fetch_account(acct_id))

        log.info("Fetching airtable data...")
        cfg = get_config()
        tables = defaultdict(dict)
        for k, v in cfg["airtable"].items():
            for k2 in v.keys():
                if k2 in ("base_id", "token"):
                    continue
                log.info(f"{k} {k2}...")
                tables[k][k2] = airtable.get_all_records(k, k2)

        with open(args.path, "wb") as f:
            pickle.dump(
                {
                    "neon": {
                        "events": events,
                        "accounts": accounts,
                        "clearance_codes": clearance_codes,
                    },
                    "airtable": tables,
                },
                f,
            )
        log.info("Done")
