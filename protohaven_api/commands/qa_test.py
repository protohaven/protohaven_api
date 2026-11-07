"""Tests for QA CLI commands."""

# pylint: disable=missing-function-docstring

import logging

import pytest

from protohaven_api.commands import qa as C
from protohaven_api.testing import mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    return mkcli(capsys, C)


def test_cronicle_qa_runs_non_destructive_jobs(mocker, cli):
    spec = mocker.Mock()
    spec.name = "readonly_job"
    spec.destructive = False
    spec.fn = mocker.Mock()

    ctx = mocker.Mock()
    init_connector = mocker.patch.object(C, "init_connector")
    mocker.patch.object(C, "CronicleClient")
    mocker.patch.object(C, "QAContext", return_value=ctx)
    mocker.patch.object(C.registry, "ALL_JOBS", [spec])
    verify = mocker.patch.object(C.verify, "verify_no_qa_neon_accounts")
    advance = mocker.patch.object(C, "send_advance_notice")
    ack = mocker.patch.object(C, "request_acknowledgment")
    summary = mocker.patch.object(C, "send_summary_notice")

    cli(
        "cronicle_qa",
        [
            "--api_key=key",
            "--image=img",
            "--no-advance-notice",
            "--skip-verify",
        ],
        parse_yaml=False,
    )

    init_connector.assert_called_once_with(C.Connector)
    C.CronicleClient.assert_called_once_with(  # pylint: disable=no-member
        C.get_config("cronicle/base_url") or "https://cron.protohaven.org/", "key"
    )
    spec.fn.assert_called_once_with(ctx)
    verify.assert_not_called()
    advance.assert_not_called()
    ack.assert_not_called()
    summary.assert_not_called()
    assert ctx.cleanup.cleanup.call_count == 2


def test_cronicle_qa_sends_summary_after_advance_notice(mocker, cli):
    spec = mocker.Mock()
    spec.name = "readonly_job"
    spec.destructive = False
    spec.fn = mocker.Mock()

    ctx = mocker.Mock()
    mocker.patch.object(C, "init_connector")
    mocker.patch.object(C, "CronicleClient")
    mocker.patch.object(C, "QAContext", return_value=ctx)
    mocker.patch.object(C.registry, "ALL_JOBS", [spec])
    mocker.patch.object(C.verify, "verify_no_qa_neon_accounts")
    advance = mocker.patch.object(C, "send_advance_notice")
    mocker.patch.object(C, "request_acknowledgment")
    summary = mocker.patch.object(C, "send_summary_notice")

    cli(
        "cronicle_qa",
        ["--api_key=key", "--image=img", "--skip-verify"],
        parse_yaml=False,
    )

    advance.assert_called_once()
    summary.assert_called_once_with(ctx, ["readonly_job"], [])


def test_cronicle_qa_failure_logs_job_link_without_job_log_text(mocker, caplog):
    spec = mocker.Mock()
    spec.name = "probe_events"
    spec.destructive = False

    ctx = mocker.Mock()
    ctx.last_result = None
    client = mocker.Mock()
    client.base_url = "https://cron.protohaven.org"

    mocker.patch.object(C, "init_connector")
    mocker.patch.object(C, "CronicleClient", return_value=client)
    mocker.patch.object(C, "QAContext", return_value=ctx)
    mocker.patch.object(C.registry, "ALL_JOBS", [spec])
    mocker.patch.object(C.verify, "verify_no_qa_neon_accounts")
    mocker.patch.object(C, "send_advance_notice")
    mocker.patch.object(C, "request_acknowledgment")
    mocker.patch.object(C, "send_summary_notice")
    mocker.patch.object(C.sys, "exit")

    def fail(job_id):
        ctx.last_result = mocker.Mock(job_ids=[job_id])
        raise AssertionError("missing substring")

    spec.fn.side_effect = lambda _: fail("job123")

    with caplog.at_level(logging.ERROR, logger="cli.qa"):
        C.Commands().cronicle_qa(
            [
                "--api_key=key",
                "--image=img",
                "--skip-verify",
                "--no-advance-notice",
            ],
            None,
        )

    assert "https://cron.protohaven.org/#JobDetails?id=job123" in caplog.text
    assert "secret job log contents" not in caplog.text
    C.sys.exit.assert_called_once_with(1)


def test_webhook_qa_runs_clearance(mocker, cli):
    ctx = mocker.Mock()
    init_connector = mocker.patch.object(C, "init_connector")
    mocker.patch.object(C, "_default_api_key", return_value="key")
    mocker.patch.object(C.webhooks, "WebhookQAContext", return_value=ctx)
    clearance = mocker.patch.object(C.webhooks, "test_clearance_webhook")
    new_member = mocker.patch.object(C.webhooks, "test_new_member_webhook")
    maintenance = mocker.patch.object(C.webhooks, "test_maintenance_webhook")

    cli("webhook_qa", ["clearance"], parse_yaml=False)

    init_connector.assert_called_once_with(C.Connector)
    C.webhooks.WebhookQAContext.assert_called_once_with(  # pylint: disable=no-member
        api_key="key", base_url=None, verify_ssl=True  # pragma: allowlist secret
    )
    clearance.assert_called_once_with(ctx)
    new_member.assert_not_called()
    maintenance.assert_not_called()
    ctx.restore_comms_overrides.assert_called_once()
    ctx.cleanup.cleanup.assert_called_once()
