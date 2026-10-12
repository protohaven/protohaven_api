"""CLI commands for post-deploy QA."""

import argparse
import base64
import logging
import sys

from protohaven_api.commands.decorator import arg, command
from protohaven_api.config import get_config
from protohaven_api.integrations.cronicle import CronicleClient
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.qa import registry, verify, webhooks
from protohaven_api.qa.base import CleanupError, QAContext
from protohaven_api.qa.comms import (
    request_acknowledgment,
    send_advance_notice,
    send_summary_notice,
)

log = logging.getLogger("cli.qa")


def _default_api_key() -> str:
    codes = get_config("general/external_access_codes") or {}
    for code, roles in codes.items():
        if "Automation" in roles:
            return base64.b64encode(code.encode()).decode("utf8")
    raise RuntimeError("No Automation external access code found in config")


def _fail(msg: str) -> None:
    log.error(msg)
    sys.exit(1)


class Commands:
    """Commands for running post-deploy QA suites."""

    # pylint: disable=too-many-branches,too-many-statements
    @command(
        arg(
            "--base_url",
            help="Base URL for Cronicle commands",
            type=str,
            default=None,
        ),
        arg(
            "--api_key",
            help="API key for Cronicle commands",
            type=str,
            required=True,
        ),
        arg(
            "--image",
            help="Docker image to run on Cronicle prod server",
            type=str,
            required=True,
        ),
        arg(
            "--job",
            dest="jobs",
            action="append",
            default=[],
            help="Job name to run; may be repeated (default: all non-destructive)",
        ),
        arg(
            "--command",
            dest="commands",
            action="append",
            default=[],
            help="Compatibility alias for --job; run only the named QA job(s)",
        ),
        arg(
            "--after",
            help="Compatibility flag; skip all jobs up to and including this named job",
            type=str,
            default=None,
        ),
        arg(
            "--include-destructive",
            help="Include destructive jobs",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--drive_folder_id",
            help="Dedicated Google Drive folder ID for backup job QA",
            type=str,
            default=None,
        ),
        arg(
            "--no-advance-notice",
            dest="no_advance_notice",
            action="store_true",
            help="Skip sending the QA advance notice to internal channels",
        ),
        arg(
            "--skip-verify",
            action="store_true",
            help="Skip final Neon account leak verification",
        ),
    )
    def cronicle_qa(self, args, _):
        """Run selected Cronicle QA jobs and report failures."""
        init_connector(Connector)

        specs = registry.ALL_JOBS
        if args.jobs or args.commands:
            selected = []
            for name in args.jobs + args.commands:
                spec = registry.get_job(name)
                if spec is None:
                    _fail(f"Unknown job: {name}")
                selected.append(spec)
            specs = selected
        else:
            specs = [s for s in specs if not s.destructive or args.include_destructive]

        if args.after:
            after_spec = registry.get_job(args.after)
            if after_spec is None:
                _fail(f"Unknown job: {args.after}")
            after_idx = specs.index(after_spec)
            specs = specs[after_idx + 1 :]
            if not specs:
                log.info("No jobs remain after %s", args.after)
                return

        if not specs:
            log.info("No jobs selected")
            return

        client = CronicleClient(
            args.base_url
            or get_config("cronicle/base_url")
            or "https://cron.protohaven.org/",
            args.api_key,
        )
        ctx = QAContext(
            client=client,
            image=args.image,
            drive_folder_id=args.drive_folder_id,
        )

        if not args.no_advance_notice:
            send_advance_notice(
                ctx,
                [s.name for s in specs],
                duration_minutes=max(10, 2 * len(specs)),
            )
            request_acknowledgment(
                [s.name for s in specs],
                interactive=sys.stdin.isatty() and not args.commands,
            )

        failures = []
        successes = []
        try:
            for spec in specs:
                log.info("Running QA job: %s", spec.name)
                try:
                    spec.fn(ctx)
                    log.info("PASS: %s", spec.name)
                    successes.append(spec.name)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.exception("FAIL: %s", spec.name)
                    failures.append(f"{spec.name}: {e}")
                finally:
                    try:
                        ctx.cleanup.cleanup()
                    except CleanupError as e:
                        failures.append(f"{spec.name} cleanup: {e}")

            if not args.skip_verify:
                try:
                    verify.verify_no_qa_neon_accounts()
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.exception("Final Neon verification failed")
                    failures.append(f"verify_neon: {e}")
        finally:
            try:
                ctx.cleanup.cleanup()
            except CleanupError as e:
                failures.append(f"final cleanup: {e}")

        if not args.no_advance_notice:
            try:
                send_summary_notice(ctx, successes, failures)
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Failed to send QA summary after run")

        if failures:
            log.error("QA failures:\n%s", "\n".join(failures))
            sys.exit(1)
        log.info("All QA jobs passed")

    # pylint: disable=too-many-branches
    @command(
        arg(
            "--base_url",
            help=(
                "Base URL of a running API server. Omit to run in-process "
                "so QA comms overrides apply."
            ),
            type=str,
            default=None,
        ),
        arg(
            "--user",
            help="Deprecated; QA now creates ephemeral Neon accounts automatically.",
            type=str,
            default=None,
        ),
        arg(
            "--api_key",
            help="base64-encoded Automation API key (defaults to config.yaml)",
            type=str,
            default=None,
        ),
        arg(
            "--verify_ssl",
            help="if True, prevent remote web request if SSL cert is invalid",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
        arg(
            "test",
            help=(
                "specific tests to run - one of (new_member, new_amp_member, "
                "clearance, maintenance, all)"
            ),
            nargs="?",
            default="all",
        ),
    )
    def webhook_qa(self, args, _):
        """Run webhook QA tests using the QA environment."""
        init_connector(Connector)
        ctx = webhooks.WebhookQAContext(
            api_key=args.api_key or _default_api_key(),
            base_url=args.base_url,
            verify_ssl=args.verify_ssl,
        )

        failures = []
        try:
            if args.base_url:
                log.warning(
                    "Remote webhook QA against %s cannot redirect comms on the server; "
                    "prefer running in-process (omit --base_url).",
                    args.base_url,
                )

            if args.test in ("new_member", "all"):
                log.info("Running webhook QA: new_member")
                try:
                    webhooks.test_new_member_webhook(ctx)
                    log.info("PASS: new_member")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.exception("FAIL: new_member")
                    failures.append(f"new_member: {e}")

            if args.test in ("new_amp_member", "all"):
                log.info("Running webhook QA: new_amp_member")
                try:
                    webhooks.test_new_member_webhook(ctx, is_amp=True)
                    log.info("PASS: new_amp_member")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.exception("FAIL: new_amp_member")
                    failures.append(f"new_amp_member: {e}")

            if args.test in ("clearance", "all"):
                log.info("Running webhook QA: clearance")
                try:
                    webhooks.test_clearance_webhook(ctx)
                    log.info("PASS: clearance")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.exception("FAIL: clearance")
                    failures.append(f"clearance: {e}")

            if args.test in ("maintenance", "all"):
                log.info("Running webhook QA: maintenance")
                try:
                    webhooks.test_maintenance_webhook(ctx)
                    log.info("PASS: maintenance")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    log.exception("FAIL: maintenance")
                    failures.append(f"maintenance: {e}")
        finally:
            ctx.restore_comms_overrides()
            try:
                ctx.cleanup.cleanup()
            except CleanupError as e:
                failures.append(f"webhook cleanup: {e}")

        if failures:
            log.error("QA failures:\n%s", "\n".join(failures))
            sys.exit(1)
        log.info("All webhook QA tests passed")
