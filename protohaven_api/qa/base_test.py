"""Tests for QA assertion helpers."""

# pylint: disable=missing-function-docstring

import pytest

from protohaven_api.qa.base import (
    MAX_ASSERT_LOG_CHARS,
    JobResult,
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


def test_assert_log_failures_truncate_large_output():
    big_log = "x" * (MAX_ASSERT_LOG_CHARS + 100)
    with pytest.raises(AssertionError) as err:
        assert_log_contains(big_log, ["missing"])
    message = str(err.value)
    assert len(message) <= MAX_ASSERT_LOG_CHARS + 200
    assert "[100 chars truncated]" in message
    assert "missing" in message


def test_comms_assertions():
    sent = JobResult(0, ["j"], {"j": "Sent to Discord #cronicle-automation: hi"})
    assert_sent_discord(sent)
    with pytest.raises(AssertionError):
        assert_no_comms_sent(sent)

    email = JobResult(0, ["j"], {"j": "Sent msg to qa-testing@protohaven.org"})
    assert_sent_email(email)


def test_marked_complete():
    result = JobResult(0, ["j"], {"j": "marked complete: 12345"})
    assert_marked_complete(result, "12345")
