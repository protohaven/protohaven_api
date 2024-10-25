"""Commands related to developing on the API"""
import logging
import pickle
from collections import defaultdict

from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import get_config  # pylint: disable=import-error
from protohaven_api.integrations import (  # pylint: disable=import-error
    airtable,
    neon,
    neon_base,
)

log = logging.getLogger("cli.dev")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for development"""

    def _sanitize_account(self, acc):
        """Remove sensitive demographic, financial, location and non-email contact information"""
        acc["accountCustomFields"] = [
            a
            for a in acc.get("accountCustomFields", [])
            if a.get("name")
            not in (
                "Accessibility Demographics",
                "Identity Demographics",
                "Race/Ethnicity",
                "Age",
                "Proof of Income",
                "Income Based Rate",
            )
        ]
        if acc.get("primaryContact"):
            acc["primaryContact"].update(
                {"addresses": [], "phone1": "", "phone2": "", "phone3": ""}
            )
        acc["generosityIndicator"] = None
        return acc

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
            acc, is_company = neon_base.fetch_account(acct_id)
            if acc is None:
                log.warning(f"Unable to fetch account with id {acct_id}, skipping")
            else:
                log.info(f"- Account #{acct_id}")
                acc = self._sanitize_account(acc)
                accounts[acct_id] = (
                    {"companyAccount": acc}
                    if is_company
                    else {"individualAccount": acc}
                )
                memberships[acct_id] = list(neon.fetch_memberships(acct_id))

        log.info("Fetching airtable data...")
        tables = defaultdict(dict)
        for k, v in get_config("airtable").items():
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
