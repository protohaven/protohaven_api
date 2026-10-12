"""QA tests for Cronicle prober jobs."""

# pylint: disable=missing-function-docstring

from protohaven_api.qa.base import QAContext, assert_log_contains


def test_probe_events(ctx: QAContext) -> None:
    result = ctx.run("probe_events", "em3xcyglgdj")
    assert result.code == 0
    # Cronicle prober logs do not consistently include the probed URL,
    # so only assert on the HTTP success status marker.
    assert_log_contains(result.text, ["200"])


def test_probe_homepage(ctx: QAContext) -> None:
    result = ctx.run("probe_homepage", "em403g0czew")
    assert result.code == 0
    assert_log_contains(result.text, ["200"])
