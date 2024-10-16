"""Loads config.yaml"""
import datetime
import os
import pickle
from functools import lru_cache
from string import Template

import yaml
from dateutil import tz as dtz
from dotenv import dotenv_values

# Using dateutil.tz instead of pytz here is a deliberate choice - multiple DST issues have occurred
# in this repo due to pytz's eager evaluation of time zone information.
# See https://blog.ganssle.io/articles/2018/03/pytz-fastest-footgun.html for more details.
tz = dtz.gettz("America/New_York")

MOCK_DATA_PATH = "mock_data.pkl"
ENV_DEFAULTS_PATH = ".env.default"
ENV_SECRETS_PATH = ".env.secret"
CONFIG_YAML_PATH = "config.yaml"
CONFIG_YAML_ENV = "PH_CONFIG"

# Part of Cronicle job environment variables
# https://github.com/jhuckaby/Cronicle/blob/6cf86b783f15f4d0754c7fb6e58cad0332fd79f9/docs/Plugins.md#job-environment-variables
JOB_ID_ENV = "JOB_ID"


def tznow():
    """Return current time bound to time zone; prevents datetime skew due to different
    location of server"""
    return datetime.datetime.now(tz)


@lru_cache(maxsize=1)
def load_yaml_with_env_substitution(yaml_path):
    """
    Loads a YAML file and substitutes placeholder values with corresponding environment variables.
    Placeholders in the YAML should be denoted as $VARIABLE_NAME or ${VARIABLE_NAME}.
    """

    with open(yaml_path, "r", encoding="utf8") as file:
        yaml_content = file.read()

    # Apply defaults, followed by secrets, followed by ENV overrides
    env = {
        **dotenv_values(ENV_DEFAULTS_PATH),
        **dotenv_values(ENV_SECRETS_PATH),
        **dict(os.environ),
    }

    yaml_content_with_env = Template(yaml_content).safe_substitute(env)
    return yaml.safe_load(yaml_content_with_env)


def _find(rv: dict, path: str):
    for key in path.split("/"):
        rv = rv[key]
    return rv


def get_config(path=None, default=None):
    """Fetches the config, defined either as PH_CONFIG env var or default config.yaml.
    If path is defined, returns the value located down the tree at that path, or
    the default if there was an error.
    """
    cfg_path = os.getenv(CONFIG_YAML_ENV)
    if not cfg_path:
        cfg_path = os.path.join(os.path.dirname(__file__), f"../{CONFIG_YAML_PATH}")
    data = load_yaml_with_env_substitution(cfg_path)
    if path is None:
        return data
    try:
        return _find(data, path)
    except (KeyError, TypeError):
        return default


@lru_cache(maxsize=1)
def mock_data():
    """Fetches mock data from .pkl file"""
    with open(MOCK_DATA_PATH, "rb") as f:
        return pickle.load(f)


@lru_cache(maxsize=1)
def get_execution_log_link():
    """If this process is executed asynchronously via Cronicle, return a link
    to the execution log of the job. If we're not running as part of a Cronicle job,
    return None.

    Cronicle injects environment variables upon execution of a job, including `JOB_ID`.
    This was confirmed via a call to `printenv` inside of a Cronicle job.
    """
    job_id = os.getenv(JOB_ID_ENV, None)
    if job_id:
        return f"https://www.api.protohaven.org:3013/#JobDetails?id={job_id}"
    return None


def exec_details_footer():
    """Return a formatted footer with details related to cron-style execution of this
    process.
    """
    l = get_execution_log_link()
    return "" if not l else f"\n*See [execution log]({l})*"
