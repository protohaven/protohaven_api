"""Test the warm caching class"""

import pytest

from protohaven_api.integrations.data import warm_cache as w


class C(w.WarmDict):
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


def test_warmdict_retry_behavior(mocker):
    """Test retry and notification behavior of WarmDict"""

    class TestWarmDict(w.WarmDict):
        """Test harness for WarmDict"""

        NAME = "TestDict"
        REFRESH_PD_SEC = 10
        RETRY_PD_SEC = 1

        def refresh(self):
            pass

    # Mock comms and time.sleep
    mock_send_discord = mocker.patch.object(w.comms, "send_discord_message")
    mock_sleep = mocker.patch.object(w.time, "sleep")

    wd = TestWarmDict()
    mocker.patch.object(
        wd,
        "refresh",
        side_effect=[Exception("Fail1"), Exception("Fail2"), Exception("Fail3"), None],
    )

    # Let the thread run for a few iterations
    wd.run_once()
    wd.run_once()
    wd.run_once()

    # Verify notifications after NOTIFY_AFTER_FAILURES failures
    assert mock_send_discord.call_count == 1
    assert "TestDict cache failed 3 times so far" in mock_send_discord.call_args[0][0]

    # Verify retry behavior
    assert mock_sleep.call_count >= wd.NOTIFY_AFTER_FAILURES
    assert all(call[0][0] == wd.RETRY_PD_SEC for call in mock_sleep.call_args_list)

    # Now we do a successful refresh
    wd.run_once()

    # Verify a recovery notification is sent
    assert mock_send_discord.call_count == 2
    assert "TestDict cache recovered after" in mock_send_discord.call_args[0][0]
