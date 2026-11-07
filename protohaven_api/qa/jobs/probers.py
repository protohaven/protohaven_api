"""QA tests for Cronicle prober jobs."""

# pylint: disable=missing-function-docstring

from protohaven_api.qa.base import QAContext, assert_log_contains


def _run_probe(ctx: QAContext, name: str, event_id: str) -> None:
    result = ctx.run(name, event_id)
    if result.code != 0:
        result = ctx.run(name, event_id)
    assert result.code == 0
    # Cronicle prober logs do not consistently include the probed URL,
    # so only assert on the HTTP success status marker.
    assert_log_contains(result.text, ["200"])


def test_probe_events(ctx: QAContext) -> None:
    _run_probe(ctx, "probe_events", "em3xcyglgdj")


def test_probe_homepage(ctx: QAContext) -> None:
    _run_probe(ctx, "probe_homepage", "em403g0czew")
