from protohaven_api.warm_cache import WarmCache
from protohaven_api.config import tznow
import datetime
import pytest


@pytest.fixture(name='c')
def fixture_c():
    """Provide a cache"""
    return WarmCache(lambda: [1,2,3], None, lambda k: k+1, datetime.timedelta(hours=1))

def test_warmcache_warmed(c):
    """Ensure simple fetching works while cache is warm"""
    c.run_once()

    assert c.get_if_warm(1)[0] == 2
    assert c.get_if_warm(2)[0] == 3
    assert c.get_if_warm(3)[0] == 4
    assert c.get_if_warm(4) == (None, None)

def test_warmcache_cold(c):
    """Test fetching works on a cold cache"""
    c.refresh_keys()
    # Note - not refreshing values via run_once

    assert c[1] == 2

def test_warmcache_expired_fetches(c):
    """Prior expired value should be ignored and
    a new value fetched"""
    c.put(1, 12345, tznow() - datetime.timedelta(hours=1))
    assert c[1] == 2


def test_warmcache_multiarg():
    """Prior expired value should be ignored and
    a new value fetched"""
    c = WarmCache(lambda: [[1,"a"]], None, lambda x,y: f"{x}{y}", datetime.timedelta(hours=1))
    assert c[(1,'a')] == "1a"
