"""Shared primitives for Cronicle QA tests."""

import logging
import secrets
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque

from protohaven_api.integrations import comms
from protohaven_api.qa.cronicle import CronicleClient

log = logging.getLogger("qa.base")

QA_EMAIL = "hello+qa-testing@protohaven.org"
QA_CHANNEL = "#cronicle-automation"
QA_DM = "@workshop_protohaven"


class CleanupError(RuntimeError):
    """Raised when one or more cleanup steps fail."""


@dataclass
class CleanupStack:
    """Exception-safe LIFO cleanup stack.

    Cleanup functions are called in reverse registration order. If any
    cleanup step fails, a notice is sent to #cronicle-automation and a
    CleanupError is raised at the end.
    """

    _steps: Deque[tuple[str, Callable[[], Any]]] = field(
        default_factory=deque, init=False
    )

    def register(self, desc: str, fn: Callable[[], Any]) -> None:
        """Register a cleanup callback."""
        self._steps.append((desc, fn))

    def cleanup(self) -> None:
        """Run all registered cleanup callbacks."""
        failures: list[str] = []
        while self._steps:
            desc, fn = self._steps.pop()
            try:
                log.info(f"QA cleanup: {desc}")
                fn()
            except Exception as e:  # pylint: disable=broad-exception-caught
                log.exception(f"QA cleanup failed: {desc}")
                failures.append(f"- {desc}: {e}")
        if failures:
            body = "QA cleanup failed; manual cleanup required:\n" + "\n".join(failures)
            try:
                comms.send_discord_message(body, QA_CHANNEL, blocking=False)
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Failed to send QA cleanup failure notice")
            raise CleanupError(body)


@dataclass
class QAContext:
    """Runtime context shared by all QA job tests."""

    client: CronicleClient
    image: str
    run_id: str = field(default_factory=lambda: secrets.token_hex(4))
    cleanup: CleanupStack = field(default_factory=CleanupStack)
    drive_folder_id: str | None = None

    def __post_init__(self) -> None:
        self._schedule: dict[str, dict[str, Any]] | None = None

    def schedule(self) -> dict[str, dict[str, Any]]:
        """Fetch and cache the Cronicle schedule, indexed by event ID."""
        if self._schedule is None:
            self._schedule = {
                row["id"]: row for row in self.client.schedule().get("rows", [])
            }
        return self._schedule

    def event_params(self, event_id: str) -> dict[str, Any]:
        """Return configured params for a Cronicle event."""
        row = self.schedule().get(event_id, {})
        params = row.get("params", {})
        if isinstance(params, dict):
            return params
        return row

    def event_args(self, event_id: str) -> str:
        """Return configured ARGS for an event, or empty string."""
        return str(self.event_params(event_id).get("ARGS", "") or "")

    # pylint: disable=too-many-arguments
    def run(
        self,
        name: str,
        event_id: str,
        args: str = "",
        *,
        send_comms: bool = False,
        dm: bool = False,
        params: dict[str, Any] | None = None,
    ):
        """Run a Cronicle event with QA comm overrides."""
        p = {
            "ARGS_CHAN_OVERRIDE": QA_CHANNEL,
            "ARGS_EMAIL_OVERRIDE": QA_EMAIL,
        }
        if dm:
            p["ARGS_DM_OVERRIDE"] = QA_DM
        if send_comms:
            p["ARGS_SEND_COMMS"] = "1"
            p["ARGS_YAML_OUT"] = f"/tmp/qa_{name}_{self.run_id}.yaml"
        else:
            p["ARGS_SEND_COMMS"] = "0"
            p["ARGS_YAML_OUT"] = ""
        if args:
            p["ARGS"] = args
        if params:
            p.update(params)
        return self.client.run_and_fetch_logs(event_id, self.image, p)


@dataclass
class JobResult:
    """Result of a Cronicle QA job run."""

    code: int
    job_ids: list[str]
    logs: dict[str, str]

    @property
    def text(self) -> str:
        """Combined log text for assertions."""
        return "\n".join(self.logs.values())


def assert_log_contains(log_text: str, substrings: list[str]) -> None:
    """Assert that each substring appears in the given log text."""
    missing = [s for s in substrings if s not in log_text]
    assert not missing, f"Expected log substrings missing: {missing}\n{log_text}"


def assert_log_not_contains(log_text: str, substrings: list[str]) -> None:
    """Assert that none of the substrings appear in the given log text."""
    present = [s for s in substrings if s in log_text]
    assert not present, f"Unexpected log substrings found: {present}\n{log_text}"


def assert_sent_discord(result: JobResult, channel: str = QA_CHANNEL) -> None:
    """Assert that a Discord message was sent to the override channel."""
    assert result.code == 0
    assert_log_contains(result.text, [f"Sent to Discord {channel}:"])


def assert_sent_email(result: JobResult, email: str = QA_EMAIL) -> None:
    """Assert that an email was sent to the override address."""
    assert result.code == 0
    assert_log_contains(result.text, ["Sent msg", email])


def assert_no_comms_sent(result: JobResult) -> None:
    """Assert that no comms were sent during the job."""
    assert result.code == 0
    assert_log_not_contains(result.text, ["Sent to Discord", "Sent msg"])


def assert_marked_complete(result: JobResult, gid: str | None = None) -> None:
    """Assert that an Asana task completion side effect executed."""
    needles = ["marked complete:"]
    if gid:
        needles.append(gid)
    assert_log_contains(result.text, needles)
