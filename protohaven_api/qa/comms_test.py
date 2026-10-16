"""Tests for QA comm helpers."""

# pylint: disable=missing-function-docstring

from protohaven_api.qa import comms


def test_send_summary_notice_lists_successes_and_failures(mocker):
    ctx = mocker.Mock()
    ctx.run_id = "abc123"
    send = mocker.patch.object(comms.comms, "send_discord_message")

    comms.send_summary_notice(ctx, ["probe_events"], ["probe_homepage: boom"])

    args = send.call_args.args
    body = args[0]
    assert args[1] == "#qa-automation"
    assert "1 passed, 1 failed" in body
    assert "Passed:" in body
    assert "- probe_events" in body
    assert "Failed:" in body
    assert "- probe_homepage: boom" in body
