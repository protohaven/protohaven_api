"""Provide an implementation of a dictionary that prefetches its data and
keeps it fresh"""
import logging
import time
from threading import Lock, Thread

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
