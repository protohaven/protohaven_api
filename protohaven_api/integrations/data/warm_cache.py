"""Provide an implementation of a dictionary that prefetches its data and
keeps it fresh"""

import logging
import time
import traceback
from threading import Lock, Thread

from protohaven_api.integrations import comms

BATCH_SZ = 5


class WarmDict:
    """Resolves keys to values and keeps the values fresh.
    Retries failures on a tighter loop, and notifies to
    Discord if there are many consecutive failures.
    """

    NAME = ""
    REFRESH_PD_SEC: float | None = None
    RETRY_PD_SEC: float | None = None
    NOTIFY_AFTER_FAILURES = 3
    NOTIFY_CHANNEL = None

    def __init__(self):
        self.log = logging.getLogger(f"WarmCache({self.NAME})")
        self.mu = Lock()
        self.cache = {}
        self.failures = 0

    def refresh(self):
        """To be implemented by inheritor"""
        raise NotImplementedError()

    def start(self, delay=0):
        """Start the refreshing process async"""
        self.log.info("Starting thread")
        Thread(target=self.run, args=(delay,), daemon=True).start()

    def __setitem__(self, k, v):
        """Put timestamped value in cache at key k"""
        with self.mu:
            self.cache[k] = v

    def __len__(self):
        with self.mu:
            return len(self.cache)

    def run_once(self):
        """Periodically repopulate keys, refresh values"""
        try:
            self.refresh()
            if self.failures >= self.NOTIFY_AFTER_FAILURES:
                comms.send_discord_message(
                    f"{self.NAME} cache recovered after {self.failures} failures",
                    "#membership-automation",
                    blocking=False,
                )
                self.failures = 0

            if self.REFRESH_PD_SEC:
                time.sleep(self.REFRESH_PD_SEC)
        except Exception:  # pylint: disable=broad-exception-caught
            traceback.print_exc()
            self.failures += 1
            if self.failures == self.NOTIFY_AFTER_FAILURES:
                comms.send_discord_message(
                    f"{self.NAME} cache failed {self.failures} times so far "
                    + f"- retry interval {self.RETRY_PD_SEC}s",
                    "#membership-automation",
                    blocking=False,
                )

            if self.RETRY_PD_SEC:
                self.log.warning(f"Retrying cache refresh in {self.RETRY_PD_SEC}s")
                time.sleep(self.RETRY_PD_SEC)

    def run(self, delay):
        """Continuously run the cache"""
        if delay:
            self.log.info(f"Waiting {delay}s before first fetch")
            time.sleep(delay)
            self.log.info("Entering runloop")
        while True:
            self.run_once()

    def get(self, k, default=None):
        """ "Matches dict.get"""
        with self.mu:
            return self.cache.get(k, default)

    def __getitem__(self, k):
        with self.mu:
            return self.cache[k]
