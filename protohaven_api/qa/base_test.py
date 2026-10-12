"""Tests for QA assertion helpers."""

# pylint: disable=missing-function-docstring

import pytest

from protohaven_api.qa.base import (
    QA_CHANNEL,
    JobResult,
    QAContext,
    assert_log_contains,
    assert_log_not_contains,
    assert_marked_complete,
    assert_no_comms_sent,
    assert_sent_discord,
    assert_sent_email,
)


def test_assert_log_contains():
    assert_log_contains("hello world", ["hello"])
    with pytest.raises(AssertionError):
        assert_log_contains("hello world", ["missing"])


def test_assert_log_not_contains():
    assert_log_not_contains("hello world", ["missing"])
    with pytest.raises(AssertionError):
        assert_log_not_contains("hello world", ["hello"])


def test_assert_log_failures_do_not_include_job_log_text():
    with pytest.raises(AssertionError) as err:
        assert_log_contains("secret job log contents", ["missing"])
    message = str(err.value)
    assert "missing" in message
    assert "secret job log contents" not in message


def test_qa_context_run_stores_last_result(mocker):
    client = mocker.Mock()
    result = mocker.Mock()
    client.run_and_fetch_logs.return_value = result
    ctx = QAContext(client=client, image="img")
    mocker.patch.object(ctx, "event_params", return_value={})

    out = ctx.run("probe_events", "em3xcyglgdj")

    assert out is result
    assert ctx.last_result is result


def test_comms_assertions():
    sent = JobResult(0, ["j"], {"j": f"Sent to Discord {QA_CHANNEL}: hi"})
    assert_sent_discord(sent)
    with pytest.raises(AssertionError):
        assert_no_comms_sent(sent)

    email = JobResult(0, ["j"], {"j": "Sent msg to qa-testing@protohaven.org"})
    assert_sent_email(email)


def test_marked_complete():
    result = JobResult(0, ["j"], {"j": "marked complete: 12345"})
    assert_marked_complete(result, "12345")
