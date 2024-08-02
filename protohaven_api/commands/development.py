"""Commands related to developing on the API"""
import logging
import pickle
from collections import defaultdict

from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import get_config  # pylint: disable=import-error
from protohaven_api.integrations import airtable, neon  # pylint: disable=import-error

log = logging.getLogger("cli.dev")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for development"""

    def _sanitize_account(self, row):
        """Remove sensitive demographic, financial, location and non-email contact information"""
        acc = row.get("individualAccount", None)
        if not acc:
            acc = row["companyAccount"]
        acc["accountCustomFields"] = [
            a
            for a in acc["accountCustomFields"]
            if a["name"]
            not in (
                "Accessibility Demographics",
                "Identity Demographics",
                "Race/Ethnicity",
                "Age",
                "Proof of Income",
                "Income Based Rate",
            )
        ]

        acc["primaryContact"]["addresses"] = []
        acc["primaryContact"]["phone1"] = ""
        acc["primaryContact"]["phone2"] = ""
        acc["primaryContact"]["phone3"] = ""
        acc["generosityIndicator"] = None
        return row

    @command(
        arg("--path", help="Path to destination file", type=str, required=True),
        arg("--after", help="Earliest date for event data", type=str, required=True),
    )
    def gen_mock_data(self, args):  # pylint: disable=too-many-locals
        """Fetch mock data from airtable, neon etc.
        Write this to a file for running without touching production data"""
        log.info("Fetching events from neon...")
        events = {
            e["id"]: e for e in neon.fetch_events(after=dateparser.parse(args.after))
        }

        log.info(f"Fetching event attendees for {len(events)} event(s)...")
        attendees = {}
        for e in events.keys():
            log.info(f"- Event #{e}")
            attendees[e] = list(neon.fetch_attendees(e))

        log.info("Fetching clearance codes from neon...")
        clearance_codes = neon.fetch_clearance_codes()

        log.info("Fetching accounts from neon...")
        accounts = {}
        memberships = {}
        for acct_id in [
            27,  # Sarah Neilsen (board)
            1245,  # Scott Martin (board)
            21,  # Karen Kocher (Tech Lead & Instructor)
            1242,  # Max Oddi (Tech)
            339,  # Brian Rooker (Instructor)
            1797,  # Test Member
            1727,  # Testing Nonmember
            1260,  # William Hart (Instructor, Tech Lead)
        ]:
            acc = neon.fetch_account(acct_id)
            if acc is None:
                log.warning(f"Unable to fetch account with id {acct_id}, skipping")
            else:
                log.info(f"- Account #{acct_id}")
                accounts[acct_id] = self._sanitize_account(acc)
                memberships[acct_id] = list(neon.fetch_memberships(acct_id))

        log.info("Fetching airtable data...")
        cfg = get_config()
        tables = defaultdict(dict)
        for k, v in cfg["airtable"].items():
            for k2 in v.keys():
                if k2 in ("base_id", "token"):
                    continue
                log.info(f"- {k} {k2}...")
                tables[k][k2] = airtable.get_all_records(k, k2)

        with open(args.path, "wb") as f:
            pickle.dump(
                {
                    "neon": {
                        "events": events,
                        "attendees": attendees,
                        "accounts": accounts,
                        "memberships": memberships,
                        "clearance_codes": clearance_codes,
                    },
                    "airtable": tables,
                },
                f,
            )
        log.info("Done")
