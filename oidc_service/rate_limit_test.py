"""Tests for in-memory rate limiting, lockout, and used-code cleanup."""

from oidc_service import auth_codes, rate_limit


def test_rate_limiter_blocks_after_limit():
    """A key is rejected once it exceeds its sliding-window allowance."""
    limiter = rate_limit.RateLimiter(max_requests=2, window_sec=60)
    assert limiter.allow("ip")
    assert limiter.allow("ip")
    assert not limiter.allow("ip")


def test_rate_limiter_window_expires():
    """A key can make requests again after its window passes."""
    limiter = rate_limit.RateLimiter(max_requests=1, window_sec=10)
    assert limiter.allow("ip", now=100.0)
    assert not limiter.allow("ip", now=105.0)
    assert limiter.allow("ip", now=110.1)


def test_lockout_manager_locks_after_threshold():
    """A key is locked out once repeated failures cross the threshold."""
    manager = rate_limit.LockoutManager(threshold=2, lockout_sec=60)
    assert not manager.record_failure("key", now=100.0)
    assert manager.record_failure("key", now=101.0)
    assert manager.is_locked("key", now=102.0)


def test_lockout_manager_expires():
    """A lockout ends after the configured duration."""
    manager = rate_limit.LockoutManager(threshold=1, lockout_sec=30)
    assert manager.record_failure("key", now=100.0)
    assert manager.is_locked("key", now=100.0)
    assert not manager.is_locked("key", now=130.1)


def test_lockout_manager_reset_clears_failures():
    """A successful authentication clears previous failures."""
    manager = rate_limit.LockoutManager(threshold=2, lockout_sec=30)
    assert not manager.record_failure("key", now=100.0)
    manager.reset("key")
    assert not manager.record_failure("key", now=200.0)
    assert manager.record_failure("key", now=201.0)
    assert manager.is_locked("key", now=201.0)


def test_used_code_store_marks_once_and_cleans_up():
    """Used-code jtis are single-use and expire after their TTL."""
    store = auth_codes.UsedCodeStore(ttl_sec=100)
    assert not store.contains_and_mark("jti-1", now=1000.0)
    assert store.contains_and_mark("jti-1", now=1000.0)
    assert not store.contains_and_mark("jti-1", now=1100.1)
