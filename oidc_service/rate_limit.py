"""In-memory rate limiting and lockout helpers.

These helpers are intentionally simple and process-local. The OIDC service is
expected to run as a single worker; move to a shared store if that changes.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:  # pylint: disable=too-few-public-methods
    """Sliding-window request limiter keyed by an arbitrary string."""

    def __init__(self, max_requests: int, window_sec: float):
        self.max_requests = max_requests
        self.window_sec = window_sec
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)
        self._last_purge = 0.0
        self._lock = threading.Lock()

    def _purge_expired(self, now: float):
        """Drop stale events and empty keys without running on every request."""
        if now - self._last_purge < self.window_sec:
            return
        self._last_purge = now
        for key in list(self._events.keys()):
            events = self._events[key]
            while events and events[0] <= now - self.window_sec:
                events.popleft()
            if not events:
                del self._events[key]

    def allow(self, key: str, now: float | None = None) -> bool:
        """Return True and record a request when the key is under its limit."""
        now = now if now is not None else time.monotonic()
        with self._lock:
            self._purge_expired(now)
            events = self._events[key]
            while events and events[0] <= now - self.window_sec:
                events.popleft()
            if len(events) >= self.max_requests:
                return False
            events.append(now)
            return True


class LockoutManager:
    """Lock out a key after too many failures within a sliding window."""

    def __init__(
        self,
        threshold: int,
        lockout_sec: float,
        failure_window_sec: float | None = None,
    ):
        self.threshold = threshold
        self.lockout_sec = lockout_sec
        self.failure_window_sec = failure_window_sec or lockout_sec
        self._failures: defaultdict[str, deque[float]] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def _prune_failures(self, key: str, now: float):
        events = self._failures.get(key)
        if not events:
            return
        while events and events[0] <= now - self.failure_window_sec:
            events.popleft()
        if not events:
            del self._failures[key]

    def is_locked(self, key: str, now: float | None = None) -> bool:
        """Return True when the key is currently locked out."""
        now = now if now is not None else time.monotonic()
        with self._lock:
            until = self._locked_until.get(key, 0)
            if until > now:
                return True
            if until:
                self._locked_until.pop(key, None)
                self._failures.pop(key, None)
            return False

    def record_failure(self, key: str, now: float | None = None) -> bool:
        """Record a failure; return True when this failure triggered a lockout."""
        now = now if now is not None else time.monotonic()
        with self._lock:
            self._prune_failures(key, now)
            self._failures[key].append(now)
            if len(self._failures[key]) >= self.threshold:
                self._locked_until[key] = now + self.lockout_sec
                self._failures.pop(key, None)
                return True
            return False

    def reset(self, key: str):
        """Clear failure history and any active lockout for a key."""
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)
