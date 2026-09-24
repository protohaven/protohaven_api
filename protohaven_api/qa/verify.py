"""Post-QA verification helpers."""

import logging

from protohaven_api.qa.fixtures import neon as neon_fixture

log = logging.getLogger("qa.verify")


def verify_no_qa_neon_accounts() -> None:
    """Raise if any QA-created Neon accounts still exist."""
    leftovers = neon_fixture.search_qa_accounts()
    if leftovers:
        details = [
            f"- {getattr(m, 'neon_id', '?')} {getattr(m, 'email', '?')}"
            for m in leftovers
        ]
        raise RuntimeError(
            "QA Neon accounts remain after cleanup:\n" + "\n".join(details)
        )
    log.info("No QA Neon accounts remain")
