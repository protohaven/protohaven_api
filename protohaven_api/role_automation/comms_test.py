"""Test comms functions"""

from protohaven_api.role_automation import comms as c


def test_discord_role_change_dm():
    """Confirm that role change DMs are properly constructed"""
    logs = ["ASDF", "GHJK", "not associated with a Neon account"]

    # Try first with association issue
    _, body = c.discord_role_change_dm(logs, "userid")
    for l in logs:
        assert l in body
    assert "To associate your Discord membership" in body
    assert "discord_id=userid" in body

    # Association details excluded if not an issue
    _, body = c.discord_role_change_dm(logs[0:2], "userid")
    assert "To associate your Discord membership" not in body
