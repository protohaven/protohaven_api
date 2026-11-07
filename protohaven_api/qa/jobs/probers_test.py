"""Tests for Cronicle prober QA jobs."""

# pylint: disable=missing-function-docstring

from protohaven_api.qa.jobs import probers


def test_probe_events(mocker):
    ctx = mocker.Mock()
    result = mocker.Mock()
    result.code = 0
    result.text = "Success (HTTP 200 OK)"
    ctx.run.return_value = result

    probers.test_probe_events(ctx)

    ctx.run.assert_called_once_with("probe_events", "em3xcyglgdj")


def test_probe_homepage(mocker):
    ctx = mocker.Mock()
    result = mocker.Mock()
    result.code = 0
    result.text = "Success (HTTP 200 OK)"
    ctx.run.return_value = result

    probers.test_probe_homepage(ctx)

    ctx.run.assert_called_once_with("probe_homepage", "em403g0czew")
