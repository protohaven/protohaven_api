"""Tests for the QA cleanup stack."""

# pylint: disable=missing-function-docstring

import pytest

from protohaven_api.qa import base
from protohaven_api.qa.base import QA_CHANNEL, CleanupError, CleanupStack


def test_cleanup_runs_in_reverse_order():
    stack = CleanupStack()
    order = []
    stack.register("first", lambda: order.append(1))
    stack.register("second", lambda: order.append(2))
    stack.cleanup()
    assert order == [2, 1]


def test_cleanup_notifies_and_raises(mocker):
    mock_send = mocker.patch.object(base.comms, "send_discord_message")
    stack = CleanupStack()

    def boom():
        raise RuntimeError("kaboom")

    stack.register("bad step", boom)
    with pytest.raises(CleanupError):
        stack.cleanup()
    mock_send.assert_called_once()
    assert QA_CHANNEL in mock_send.call_args[0]
    assert "kaboom" in mock_send.call_args[0][0]
