"""QA tests for Cronicle prober jobs."""

from protohaven_api.qa.base import QAContext


def test_probe_events(ctx: QAContext) -> None:
    result = ctx.run("probe_events", "em3xcyglgdj")
    assert result.code == 0


def test_probe_homepage(ctx: QAContext) -> None:
    result = ctx.run("probe_homepage", "em403g0czew")
    assert result.code == 0
