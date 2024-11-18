"""Provide an implementation of a dictionary that prefetches its data and
keeps it fresh"""
import datetime
import logging
import time
from threading import Lock, Thread

from dateutil import parser as dateparser

from protohaven_api.config import tz, tznow
from protohaven_api.integrations import airtable, neon

BATCH_SZ = 5


class WarmDict:
    """Resolves keys to values and keeps the values fresh."""

    NAME = ""
    REFRESH_PD_SEC = None

    def __init__(self):
        self.log = logging.getLogger(f"WarmCache({self.NAME})")
        self.mu = Lock()
        self.cache = {}

    def refresh(self):
        """To be implemented by inheritor"""
        raise NotImplementedError()

    def start(self):
        """Start the refreshing process async"""
        self.log.info("Starting thread")
        Thread(target=self.run, daemon=True).start()

    def __setitem__(self, k, v):
        """Put timestamped value in cache at key k"""
        with self.mu:
            self.cache[k] = v

    def __len__(self):
        with self.mu:
            return len(self.cache)

    def run(self):
        """Periodically repopulate keys, refresh values"""
        while True:
            # try:
            self.refresh()
            # except Exception as e:
            #    self.log.error(str(e))
            if self.REFRESH_PD_SEC:
                time.sleep(self.REFRESH_PD_SEC)

    def get(self, k, default=None):
        """ "Matches dict.get"""
        with self.mu:
            return self.cache.get(k, default)

    def __getitem__(self, k):
        with self.mu:
            return self.cache[k]


# Sign-ins need to be speedy; if it takes more than half a second, folks will
# disengage.
class AccountCache(WarmDict):
    """Prefetches account information for faster lookup.
    Lookups are case-insensitive (to match email spec)"""

    NAME = "neon_accounts"
    REFRESH_PD_SEC = datetime.timedelta(hours=24).total_seconds()
    FIELDS = [
        *neon.MEMBER_SEARCH_OUTPUT_FIELDS,
        "Email 1",
        neon.CustomField.ACCOUNT_AUTOMATION_RAN,
    ]

    def get(self, k, default=None):
        return super().get(str(k).lower(), default)

    def __setitem__(self, k, v):
        return super().__setitem__(str(k).lower(), v)

    def __getitem__(self, k):
        return super().__getitem__(str(k).lower())

    def _update(self, a):
        d = self.get(a["Email 1"], {})
        d[a["Account ID"]] = a
        self[a["Email 1"]] = d

    def refresh(self):
        """Refresh values; called every REFRESH_PD"""
        self.log.info("Beginning AccountCache refresh")
        n = 0
        for a in neon.get_inactive_members(self.FIELDS):
            self._update(a)
            n += 1
            if n % 100 == 0:
                self.log.info(n)
        for a in neon.get_active_members(self.FIELDS):
            self._update(a)
            n += 1
            if n % 100 == 0:
                self.log.info(n)
        self.log.info(f"Fetched {n} total accounts")


class AirtableCache(WarmDict):
    """Prefetches airtable data for faster lookup"""

    NAME = "airtable"
    REFRESH_PD_SEC = datetime.timedelta(hours=24).total_seconds()

    def refresh(self):
        """Refresh values; called every REFRESH_PD"""
        self.log.info("Beginning AirtableCache refresh")
        self["announcements"] = airtable.get_all_announcements()
        self["violations"] = airtable.get_policy_violations()
        self.log.info("AirtableCache refresh complete")

    def violations_for(self, account_id):
        """Check member for storage violations"""
        for pv in self["violations"]:
            if str(pv["fields"].get("Neon ID")) != str(account_id) or pv["fields"].get(
                "Closure"
            ):
                continue
            yield pv

    def announcements_after(self, d, roles, clearances):
        """Gets all announcements, excluding those before `d`"""
        now = tznow()
        for row in self["announcements"]:
            adate = dateparser.parse(
                row["fields"].get("Published", "2024-01-01")
            ).astimezone(tz)
            if adate <= d or adate > now:
                continue

            tools = set(row["fields"].get("Tool Name (from Tool Codes)", []))
            if len(tools) > 0:
                cleared_for_tool = False
                for c in clearances:
                    if c in tools:
                        cleared_for_tool = True
                        break
                if not cleared_for_tool:
                    continue

            for r in row["fields"]["Roles"]:
                if r in roles:
                    row["fields"]["rec_id"] = row["id"]
                    yield row["fields"]
                    break
