"""Test the warm caching class"""
import pytest
from dateutil import parser as dateparser

from protohaven_api.automation.membership import warm_cache as w
from protohaven_api.config import tz


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


@pytest.mark.parametrize(
    "desc, data, want",
    [
        (
            "correct role & tool code",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": ["Sandblaster"],
            },
            True,
        ),
        (
            "correct role, non cleared tool code",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": ["Planer"],
            },
            False,
        ),
        (
            "wrong role, cleared tool",
            {
                "Published": "2024-04-01",
                "Roles": ["badrole"],
                "Tool Name (from Tool Codes)": ["Sandblaster"],
            },
            False,
        ),
        (
            "Correct role, no tool",
            {
                "Published": "2024-04-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            True,
        ),
        (
            "too old",
            {
                "Published": "2024-03-01",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            False,
        ),
        (
            "too new (scheduled)",
            {
                "Published": "2024-05-05",
                "Roles": ["role1"],
                "Tool Name (from Tool Codes)": [],
            },
            False,
        ),
    ],
)
def test_get_announcements_after(
    desc, data, want, mocker
):  # pylint: disable=unused-argument
    """Test announcement fetching"""
    tc = w.AirtableCache()
    tc["announcements"] = [{"fields": data, "id": "123"}]
    mocker.patch.object(
        w, "tznow", return_value=dateparser.parse("2024-04-02").astimezone(tz)
    )
    got = list(
        tc.announcements_after(
            dateparser.parse("2024-03-14").astimezone(tz),
            ["role1"],
            ["SBL: Sandblaster"],
        )
    )
    if want:
        assert got
    else:
        assert not got


def test_get_storage_violations():
    """Test checking member for storage violations"""
    account_id = "123"
    tc = w.AirtableCache()
    tc["violations"] = [
        {"fields": {"Neon ID": account_id, "Violation": "Excessive storage"}},
        {"fields": {"Neon ID": "456", "Closure": "2023-10-01"}},
        {"fields": {"Neon ID": account_id, "Closure": "2023-10-01"}},
    ]

    violations = list(tc.violations_for(account_id))

    assert len(violations) == 1
    assert violations[0]["fields"]["Violation"] == "Excessive storage"
    assert "Closure" not in violations[0]["fields"]


def test_account_cache_case_insensitive(mocker):
    """Confirm that lookups are case insensitive, and that non-string
    types are handled safely"""
    mocker.patch.object(w.neon, "get_inactive_members", return_value=[])
    want1 = {"Email 1": "aSdF", "Account ID": 123}
    mocker.patch.object(w.neon, "get_active_members", return_value=[want1])
    c = w.AccountCache()
    c.refresh()
    c["gHjK"] = "test"
    c[None] = "foo"
    assert c["AsDf"][123] == want1
    assert c["GhJk"] == "test"
    assert c.get("GhJk") == "test"
    assert c["nonE"] == "foo"


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
    assert "Failed to update cache 3 times so far" in mock_send_discord.call_args[0][0]

    # Verify retry behavior
    assert mock_sleep.call_count >= wd.NOTIFY_AFTER_FAILURES
    assert all(call[0][0] == wd.RETRY_PD_SEC for call in mock_sleep.call_args_list)

    # Now we do a successful refresh
    wd.run_once()

    # Verify a recovery notification is sent
    assert mock_send_discord.call_count == 2
    assert "Successfully updated cache after" in mock_send_discord.call_args[0][0]
