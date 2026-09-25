"""QA comm overrides and advance notices."""

import logging

from protohaven_api.integrations import comms
from protohaven_api.qa.base import QA_CHANNEL, QA_EMAIL, QAContext

log = logging.getLogger("qa.comms")


def send_advance_notice(
    ctx: QAContext,
    job_names: list[str],
    duration_minutes: int = 30,
    failure_channels: tuple[str, ...] = (),
) -> None:
    """Warn internal channels before QA tests run."""
    names = "\n".join(f"- {n}" for n in job_names)
    failure_warning = ""
    if failure_channels:
        failure_warning = (
            "\n\nFailure-path tests may also send direct notifications to: "
            + ", ".join(failure_channels)
        )
    body = (
        "Cronicle QA starting; the following jobs will run against prod "
        f"credentials (run_id={ctx.run_id}, expected duration ~"
        f"{duration_minutes} minutes):\n{names}\n\n"
        "Mock prod data (Neon accounts, Airtable records, Asana tasks, Booked "
        "resources/reservations, and Drive files) will be created and cleaned "
        "up automatically.\n"
        f"All generated alerts are overridden to {QA_CHANNEL}; email is "
        f"overridden to {QA_EMAIL}; DMs are overridden to the dedicated QA "
        "Discord user (workshop_protohaven). No action is needed unless a "
        "cleanup failure notice follows."
        f"{failure_warning}"
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


def request_acknowledgment(job_names: list[str], interactive: bool = True) -> None:
    """Require operator acknowledgment before running QA jobs.

    Non-interactive runs log a warning and continue; this keeps Cronicle-
    launched automation usable while preserving the manual safety gate.
    """
    names = ", ".join(job_names)
    prompt = f'Type "run {names}" to continue: '
    if not interactive:
        log.warning(
            "Not attached to an interactive terminal; skipping advance-notice "
            "acknowledgment for: %s",
            names,
        )
        return
    answer = input(prompt)
    if answer.strip() != f"run {names}":
        raise RuntimeError("Advance-notice acknowledgment failed; aborting QA run")
