"""Compatibility wrapper for webhook QA.

Use the CLI command instead:

    python3 -m protohaven_api.cli webhook_qa clearance
"""

import base64
import sys

from protohaven_api.commands.qa import Commands
from protohaven_api.config import get_config
from protohaven_api.integrations.cronicle import Progress
from protohaven_api.qa import webhooks


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


def main() -> int:
    """Run webhook QA through the CLI command."""
    Commands().webhook_qa(sys.argv[1:], Progress())
    return 0


if __name__ == "__main__":
    sys.exit(main())
