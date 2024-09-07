"""Loads config.yaml"""
import datetime
from functools import cache
from os import getenv

import pytz
import yaml

tz = pytz.timezone("US/Eastern")


def tznow():
    """Return current time bound to time zone; prevents datetime skew due to different
    location of server"""
    return datetime.datetime.now(tz)


@cache
def get_config():
    """Fetches the config"""
    with open(getenv("PH_CONFIG", "config.yaml"), "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


@cache
def get_execution_log_link():
    """If this process is executed asynchronously via Cronicle, return a link
    to the execution log of the job. If we're not running as part of a Cronicle job,
    return None.

    Cronicle injects environment variables upon execution of a job, including `JOB_ID`.
    This was confirmed via a call to `printenv` inside of a Cronicle job.
    """
    job_id = getenv("JOB_ID", None)
    if job_id:
        return f"https://www.api.protohaven.org:3013/#JobDetails?id={job_id}"
    return None


def exec_details_footer():
    """Return a formatted footer with details related to cron-style execution of this
    process.
    """
    l = get_execution_log_link()
    return "" if not l else "\nExecution log: " + l
