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
            dateparser.parse("2024-03-14").astimezone(tz), ["role1"], ["Sandblaster"]
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
