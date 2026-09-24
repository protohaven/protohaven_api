"""Integration tests for Cronicle jobs/events."""

import argparse
import logging
import sys

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.qa import registry, verify
from protohaven_api.qa.base import CleanupError, QAContext
from protohaven_api.qa.comms import request_acknowledgment, send_advance_notice
from protohaven_api.qa.cronicle import CronicleClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("cronicle_qa")


# pylint: disable=too-many-branches,too-many-statements
def main() -> int:
    """Run selected Cronicle QA jobs and report failures."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base_url",
        default=get_config("cronicle/base_url") or "https://cron.protohaven.org/",
        help="Base URL for Cronicle commands",
    )
    parser.add_argument(
        "--api_key",
        "--key",
        dest="api_key",
        required=True,
        help="API key for Cronicle commands",
    )
    parser.add_argument(
        "--image",
        required=True,
        help="Docker image to run on Cronicle prod server (e.g. protohaven_api:0.20.1)",
    )
    parser.add_argument(
        "--job",
        dest="jobs",
        action="append",
        default=[],
        help="Job name to run; may be repeated (default: all non-destructive)",
    )
    parser.add_argument(
        "--command",
        dest="commands",
        action="append",
        default=[],
        help="Compatibility alias for --job; run only the named QA job(s)",
    )
    parser.add_argument(
        "--after",
        help="Compatibility flag; skip all jobs up to and including this named job",
    )
    parser.add_argument(
        "--include-destructive",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Include destructive jobs",
    )
    parser.add_argument(
        "--drive_folder_id",
        default=None,
        help="Dedicated Google Drive folder ID for backup job QA",
    )
    parser.add_argument(
        "--no-advance-notice",
        "--skip-advance-notice",
        dest="no_advance_notice",
        action="store_true",
        help="Skip sending the QA advance notice to internal channels",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip final Neon account leak verification",
    )
    args = parser.parse_args()

    init_connector(Connector)

    specs = registry.ALL_JOBS
    if args.jobs or args.commands:
        selected = []
        for name in args.jobs + args.commands:
            spec = registry.get_job(name)
            if spec is None:
                parser.error(f"Unknown job: {name}")
            selected.append(spec)
        specs = selected
    else:
        specs = [s for s in specs if not s.destructive or args.include_destructive]

    if args.after:
        after_spec = registry.get_job(args.after)
        if after_spec is None:
            parser.error(f"Unknown job: {args.after}")
        after_idx = specs.index(after_spec)
        specs = specs[after_idx + 1 :]
        if not specs:
            log.info("No jobs remain after %s", args.after)
            return 0

    if not specs:
        log.info("No jobs selected")
        return 0

    client = CronicleClient(args.base_url, args.api_key)
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
            failure_channels=(
                "#tech-automation",
                "#class-automation",
                "#tool-automation",
                "#membership-automation",
            ),
        )
        request_acknowledgment(
            [s.name for s in specs],
            interactive=sys.stdin.isatty() and not args.commands,
        )

    failures = []
    try:
        for spec in specs:
            log.info(f"Running QA job: {spec.name}")
            try:
                spec.fn(ctx)
                log.info(f"PASS: {spec.name}")
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.exception(f"FAIL: {spec.name}")
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

    if failures:
        log.error("QA failures:\n%s", "\n".join(failures))
        return 1
    log.info("All QA jobs passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
