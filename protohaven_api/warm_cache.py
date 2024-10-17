from threading import Lock, Thread
import time
from protohaven_api.config import tznow

BATCH_SZ = 5

class WarmCache:
    """Resolves keys to values and keeps the values fresh"""

    def __init__(self, keys_fn, keys_fetch_interval, value_fn, value_fetch_interval, run=True):
        self.keys_fn = keys_fn
        self.keys_fetch_interval = keys_fetch_interval
        self.value_fn = value_fn
        self.value_fetch_interval = value_fetch_interval
        self.mu = Lock()
        self.cache = {}
        self.last_key_fetch = None
        if run:
            Thread(target=self.run, daemon=True)

    def put(self, k, v, t):
        """Put timestamped value in cache at key k"""
        with self.mu:
            self.cache[k] = v, t

    def __len__(self):
        with self.mu:
            return len(self.cache)

    def refresh_keys(self):
        """Add any new keys"""
        for k in self.keys_fn():
            with self.mu:
                if k in self.cache:
                    continue
            self.put(k if isinstance(k, tuple) else (k,), None, None)

    def refresh_values(self, batch_sz=BATCH_SZ, now=None):
        """Refresh up to batch_sz stale values"""
        now = now or tznow()
        cold_thresh = now - self.value_fetch_interval
        cold_keys = []
        with self.mu:
            for k, vv in self.cache.items():
                v, t = vv
                if v is None or t < cold_thresh:
                    cold_keys.append(k)
        for cold in cold_keys[:batch_sz]:
            self.put(cold, self.value_fn(*cold), now)


    def run_once(self):
        """Do updates, return sleep duration"""
        now = tznow()
        if not self.last_key_fetch or (now - self.last_key_fetch) > self.keys_fetch_interval:
            self.refresh_keys()
            self.last_key_fetch = now
        self.refresh_values(now=now)
        return (self.value_fetch_interval / max(1, len(self))).seconds

    def run(self):
        """Periodically repopulate keys, refresh values"""
        while True:
            time.sleep(self.run_once())

    def get_if_warm(self, key, now=None):
        """Fetch and return cached value, or (None, None) if expired"""
        now = now or tznow()
        with self.mu:
            v, t = self.cache.get(key if isinstance(key, tuple) else (key,), (None, None))
            if v is not None and t is not None and (now - t) < self.value_fetch_interval:
                return v, t
        return None, None


    def __getitem__(self, key, default=None):
        now = tznow()
        v, t = self.get_if_warm(key, now)
        if not t:
            v = self.value_fn(*(key if isinstance(key, tuple) else (key,)))
            self.put(key,v,now)
        return v or default
