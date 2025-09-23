"""Convenience methods for acting as a Cronicle job"""

from functools import lru_cache
from os import getenv

from protohaven_api.config import get_config

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
