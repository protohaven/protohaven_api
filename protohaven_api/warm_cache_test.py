"""Test the warm caching class"""
import pytest

from protohaven_api.warm_cache import WarmDict


class C(WarmDict):
    """Simple test class"""

    def refresh(self):
        """Simple refresh action"""
        self[1] = "a"


def test_warmcache_basic():
    """Ensure simple fetching works while cache is warm"""
    c = C()
    c.refresh()
    assert c[1] == "a"
    assert c.get(1) == "a"
    with pytest.raises(KeyError):
        _ = c[2]
