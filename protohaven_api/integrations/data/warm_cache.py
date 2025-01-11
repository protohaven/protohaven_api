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

    def __init__(
        self,
        retry_sec,
        refresh_sec,
        notify_after_failures,
        notify_channel,
        enabled=None,
        start_delay=0,
    ):
        self.retry_sec = retry_sec
        self.refresh_sec = refresh_sec
        self.notify_after_failures = notify_after_failures
        self.notify_channel = notify_channel
        self.log = logging.getLogger(f"WarmCache({self.__class__.__name__})")
        self.mu = Lock()
        self.cache = {}
        self.failures = 0
        self.delay = start_delay

    def refresh(self):
        """To be implemented by inheritor"""
        raise NotImplementedError()

    def start(self):
        """Start the refreshing process async"""
        self.log.info("Starting thread")
        Thread(target=self.run, args=(self.delay,), daemon=True).start()

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
            if self.failures >= self.notify_after_failures:
                comms.send_discord_message(
                    f"{self.__class__.__name__} cache recovered after {self.failures} failures",
                    "#membership-automation",
                    blocking=False,
                )
                self.failures = 0

            if self.refresh_sec:
                time.sleep(self.refresh_sec)
        except Exception:  # pylint: disable=broad-exception-caught
            traceback.print_exc()
            self.failures += 1
            if self.failures == self.notify_after_failures:
                comms.send_discord_message(
                    f"{self.__class__.__name__} cache failed {self.failures} times so far "
                    + f"- retry interval {self.retry_sec}s",
                    "#membership-automation",
                    blocking=False,
                )

            if self.retry_sec:
                self.log.warning(f"Retrying cache refresh in {self.retry_sec}s")
                time.sleep(self.retry_sec)

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
