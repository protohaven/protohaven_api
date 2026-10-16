"""Convenience methods for acting as a Cronicle job and talking to its API."""

import io
import json
import logging
import tarfile
import time
from dataclasses import dataclass
from functools import lru_cache
from os import getenv
from os.path import getsize
from typing import Any

import requests
import urllib3

from protohaven_api.config import get_config

log = logging.getLogger("integrations.cronicle")

urllib3.disable_warnings()

# Part of Cronicle job environment variables
# https://github.com/jhuckaby/Cronicle/blob/6cf86b783f15f4d0754c7fb6e58cad0332fd79f9/docs/Plugins.md#job-environment-variables
JOB_ID_ENV = "JOB_ID"


@lru_cache(maxsize=1)
def get_execution_log_link():
    """If this process is executed asynchronously via Cronicle, return a link
    to the execution log of the job. If we're not running as part of a Cronicle job,
    return None.

    Cronicle injects environment variables upon execution of a job, including `JOB_ID`.
    This was confirmed via a call to `printenv` inside of a Cronicle job.
    """
    job_id = getenv(JOB_ID_ENV, None)
    base = get_config("cronicle/base_url")
    if job_id:
        return f"{base}/#JobDetails?id={job_id}"
    return None


def exec_details_footer():
    """Return a formatted footer with details related to cron-style execution of this
    process.
    """
    l = get_execution_log_link()
    return "" if not l else f"\n*See [execution log](<{l}>)*"


@dataclass
class JobResult:
    """Result of running a Cronicle event."""

    code: int
    job_ids: list[str]
    logs: dict[str, str]

    @property
    def text(self) -> str:
        """Combined log text for assertions."""
        return "\n".join(self.logs.values())


class CronicleClient:
    """Minimal Cronicle API client."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30,
        job_timeout: int = 60 * 30,
        poll_interval: int = 5,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.job_timeout = job_timeout
        self.poll_interval = poll_interval
        self.session = requests.Session()

    def _get(
        self, path: str, params: dict[str, Any] | None = None, raw: bool = False
    ) -> Any:
        rep = self.session.get(
            f"{self.base_url}{path}",
            headers={"X-API-Key": self.api_key},
            params=params or {},
            timeout=self.timeout,
            verify=False,
        )
        rep.raise_for_status()
        if raw:
            return rep.text
        return rep.json()

    def _post(self, path: str, data: dict[str, Any]) -> Any:
        rep = self.session.post(
            f"{self.base_url}{path}",
            headers={"X-API-Key": self.api_key},
            json=data,
            timeout=self.timeout,
            verify=False,
        )
        rep.raise_for_status()
        return rep.json()

    def schedule(self) -> dict[str, Any]:
        """Fetch the full Cronicle event schedule."""
        return self._get("/api/app/get_schedule/v1")

    def run_event(self, event_id: str, image: str, params: dict[str, Any]) -> list[str]:
        """Start a Cronicle event and return its job IDs."""
        data = {
            "id": event_id,
            "retries": 0,
            "timeout": self.job_timeout,
            # The Cronicle docker plugin reads the image name from the
            # uppercase IMAGE job param. Put it last so it always wins over
            # any IMAGE param already configured on the event.
            "params": {**params, "IMAGE": image},
        }
        rep = self._post("/api/app/run_event/v2", data)
        if "ids" not in rep:
            raise RuntimeError(f"Cronicle run_event failed: {rep}")
        return list(rep["ids"])

    def job_status(self, job_id: str) -> dict[str, Any]:
        """Fetch status for a single Cronicle job."""
        rep = self._get("/api/app/get_job_status/v1", {"id": job_id})
        return rep.get("job", rep)

    def job_log(self, job_id: str) -> str:
        """Fetch log output for a single Cronicle job."""
        # Cronicle returns this endpoint as plain text (not JSON) in prod.
        rep = self._get("/api/app/get_job_log", {"id": job_id}, raw=True)
        if isinstance(rep, str):
            return rep
        for key in ("text", "log", "output", "rows"):
            if key in rep:
                value = rep[key]
                if isinstance(value, list):
                    return "\n".join(str(v) for v in value)
                return str(value)
        return str(rep)

    def run_and_fetch_logs(
        self, event_id: str, image: str, params: dict[str, Any]
    ) -> JobResult:
        """Run an event, wait for completion, and fetch all job logs."""
        job_ids = self.run_event(event_id, image, params)
        log.info(f"Started Cronicle event {event_id}: {job_ids}")

        start = time.monotonic()
        while True:
            complete = True
            code = None
            for job_id in job_ids:
                status = self.job_status(job_id)
                complete = complete and status.get("complete") == 1
                if status.get("complete") == 1:
                    code = status.get("code")
            if complete:
                break
            if time.monotonic() - start > self.job_timeout:
                raise TimeoutError(f"Timed out waiting for Cronicle job(s): {job_ids}")
            time.sleep(self.poll_interval)

        logs = {job_id: self.job_log(job_id) for job_id in job_ids}
        final_code = code if code is not None else 0
        outcome = "failed" if final_code != 0 else "succeeded"
        log.info(f"Cronicle job(s) {outcome}; log links:")
        for job_id in job_ids:
            log.info(f"{self.base_url}/#JobDetails?id={job_id}")
        return JobResult(code=final_code, job_ids=job_ids, logs=logs)


def schedule_backup(client: CronicleClient, output_filename: str) -> int:
    """Write the Cronicle schedule to a gzipped tar archive.

    Returns the archive size in bytes.
    """
    content = json.dumps(client.schedule(), indent=2).encode("utf-8")
    with tarfile.open(output_filename, "w:gz") as tar:
        info = tarfile.TarInfo(name="schedule.json")
        info.size = len(content)
        tar.addfile(tarinfo=info, fileobj=io.BytesIO(content))
    return getsize(output_filename)


class Progress:
    """A simple progress reporter that allows for multiple stages/loops"""

    def __init__(self, n=1, on=None):
        self.on = on or (get_execution_log_link() is not None)
        self.n = n

    def set_stages(self, n):
        """Set the number of stages of progress"""
        self.n = n

    def __setitem__(self, i, v):
        """Writes progress to stdout for reading by Cronicle.
        This is omitted if we're not running as a cronicle job."""
        pct = f"{(v + i) / self.n:.2f}"
        if self.on:
            print('{ "progress": ' + pct + " }")
