"""Integration tests for various API webhooks; see docs/qa.md

This script is now a thin wrapper around :mod:`protohaven_api.qa.webhooks`.
The webhook tests run in-process by default so comms overrides apply and
ephemeral QA Neon accounts are used instead of shared test accounts.
"""

import argparse
import base64
import logging
import sys

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.qa import webhooks
from protohaven_api.qa.base import CleanupError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("webhook_qa")


def _default_api_key() -> str:
    codes = get_config("general/external_access_codes") or {}
    for code, roles in codes.items():
        if "Automation" in roles:
            return base64.b64encode(code.encode()).decode("utf8")
    raise RuntimeError("No Automation external access code found in config")


def _ctx_from_params(params) -> webhooks.WebhookQAContext:
    api_key = params.api_key or _default_api_key()
    if isinstance(api_key, bytes):
        api_key = api_key.decode("utf8")
    return webhooks.WebhookQAContext(
        api_key=api_key,
        base_url=getattr(params, "base_url", None),
        verify_ssl=getattr(params, "verify_ssl", True),
    )


def run_user_clearances_webhook_test(params):
    """Backwards-compatible wrapper for the clearance webhook QA test."""
    ctx = _ctx_from_params(params)
    try:
        webhooks.test_clearance_webhook(ctx)
    finally:
        ctx.restore_comms_overrides()
        ctx.cleanup.cleanup()


def run_neon_membership_created_callback_test(params, is_amp=False):
    """Backwards-compatible wrapper for the new-member webhook QA test."""
    ctx = _ctx_from_params(params)
    try:
        webhooks.test_new_member_webhook(ctx, is_amp=is_amp)
    finally:
        ctx.restore_comms_overrides()
        ctx.cleanup.cleanup()


def run_get_maintenance_data_webhook_test(params):
    """Backwards-compatible wrapper for the maintenance data webhook QA test."""
    ctx = _ctx_from_params(params)
    try:
        webhooks.test_maintenance_webhook(ctx)
    finally:
        ctx.restore_comms_overrides()
        ctx.cleanup.cleanup()


# pylint: disable=too-many-branches,too-many-statements
def main() -> int:
    """Run selected webhook QA tests and report failures."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base_url",
        default=None,
        help="Base URL of a running API server. Omit to run against an in-process app "
        "so QA comms overrides apply.",
    )
    parser.add_argument(
        "--user",
        default=None,
        help="Deprecated; QA now creates ephemeral Neon accounts automatically.",
    )
    parser.add_argument(
        "--api_key",
        default=None,
        help="base64-encoded Automation API key (defaults to config.yaml)",
    )
    parser.add_argument(
        "--verify_ssl",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="if True, prevent remote web request if SSL cert is invalid",
    )
    parser.add_argument(
        "test",
        nargs="?",
        default="all",
        help="specific tests to run - one of (new_member, new_amp_member, clearance, "
        "maintenance, all)",
    )
    args = parser.parse_args()

    init_connector(Connector)
    api_key = args.api_key or _default_api_key()
    ctx = webhooks.WebhookQAContext(
        api_key=api_key,
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
        return 1
    log.info("All webhook QA tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
