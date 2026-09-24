"""QA comm overrides and advance notices."""

import logging

from protohaven_api.integrations import comms
from protohaven_api.qa.base import QA_CHANNEL, QA_EMAIL, QAContext

log = logging.getLogger("qa.comms")


def send_advance_notice(ctx: QAContext, job_names: list[str]) -> None:
    """Warn internal channels before QA tests run."""
    names = "\n".join(f"- {n}" for n in job_names)
    body = (
        "Cronicle QA starting; the following jobs will run against prod "
        f"credentials (run_id={ctx.run_id}):\n{names}\n\n"
        f"All generated alerts are overridden to {QA_CHANNEL}; email is "
        f"overridden to {QA_EMAIL}. No action is needed unless a cleanup "
        "failure notice follows."
    )
    try:
        comms.send_discord_message(body, QA_CHANNEL, blocking=True)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("Failed to send QA advance notice to Discord")
        raise
    try:
        comms.send_email(
            "Cronicle QA starting",
            body,
            [QA_EMAIL],
            False,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("Failed to send QA advance notice email")
        raise
