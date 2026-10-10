"""Post-QA verification helpers."""

import logging

from protohaven_api.integrations import comms
from protohaven_api.qa.base import QA_CHANNEL
from protohaven_api.qa.fixtures import neon as neon_fixture

log = logging.getLogger("qa.verify")


def verify_no_qa_neon_accounts(notify: bool = True) -> None:
    """Raise if any QA-created Neon accounts still exist.

    First anonymizes any legacy QA-prefixed accounts left behind by prior
    failed runs (Neon V2 has no account delete endpoint). If leftovers
    remain and ``notify`` is true, send a manual-cleanup notice to
    ``#cronicle-automation`` before raising.
    """
    try:
        neon_fixture.anonymize_legacy_qa_accounts()
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("Failed to anonymize legacy QA Neon accounts")
    leftovers = neon_fixture.search_qa_accounts()
    if leftovers:
        details = [
            f"- {getattr(m, 'neon_id', '?')} {getattr(m, 'email', '?')}"
            for m in leftovers
        ]
        body = "QA cleanup failed; manual cleanup required:\n" + "\n".join(details)
        if notify:
            try:
                comms.send_discord_message(body, QA_CHANNEL, blocking=False)
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Failed to send QA Neon leftover notice")
        raise RuntimeError(body)
    log.info("No QA Neon accounts remain")
