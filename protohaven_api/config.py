"""Loads config.yaml"""

import datetime
import os
from functools import lru_cache
from string import Template
from typing import Any, Dict, Optional

import yaml
from dateutil import tz as dtz
from dotenv import dotenv_values

# Using dateutil.tz instead of pytz here is a deliberate choice - multiple DST issues have occurred
# in this repo due to pytz's eager evaluation of time zone information.
# See https://blog.ganssle.io/articles/2018/03/pytz-fastest-footgun.html for more details.
tz = dtz.gettz("America/New_York")

# Configuration file paths
ENV_DEFAULTS_PATH = ".env.default"
ENV_SECRETS_PATH = ".env.secret"
CONFIG_YAML_PATH = "config.yaml"
CONFIG_YAML_ENV = "PH_CONFIG"


def utcnow() -> datetime.datetime:
    """Returns current time in UTC"""
    return datetime.datetime.now(dtz.UTC)


def tznow() -> datetime.datetime:
    """Return current time bound to time zone; prevents datetime skew due to different
    location of server"""
    return datetime.datetime.now(tz)


@lru_cache(maxsize=1)
def load_yaml_with_env_substitution(yaml_path: str) -> Dict[str, Any]:
    """
    Loads a YAML file and substitutes placeholder values with corresponding environment variables.
    Placeholders in the YAML should be denoted as $VARIABLE_NAME or ${VARIABLE_NAME}.
    """

    with open(yaml_path, "r", encoding="utf8") as file:
        yaml_content = file.read()

    # Apply defaults, followed by secrets, followed by ENV overrides
    env = {
        **dotenv_values(ENV_DEFAULTS_PATH),
        **(
            dotenv_values(ENV_SECRETS_PATH)
            if not os.getenv("PH_SERVER_MODE") == "dev"
            else {}
        ),
        **dict(os.environ),
    }

    yaml_content_with_env = Template(yaml_content).safe_substitute(env)
    return yaml.safe_load(yaml_content_with_env)


def _find(rv: Dict[str, Any], path: str) -> Any:
    for key in path.split("/"):
        rv = rv[key]
    return rv


def get_config(
    path: Optional[str] = None, default: Any = None, as_bool: bool = False
) -> Any:
    """Fetches the config, defined either as PH_CONFIG env var or default config.yaml.
    If path is defined, returns the value located down the tree at that path, or
    the default if there was an error.
    """
    cfg_path = os.getenv(CONFIG_YAML_ENV)
    if not cfg_path:
        cfg_path = os.path.join(os.path.dirname(__file__), f"../{CONFIG_YAML_PATH}")
    data = load_yaml_with_env_substitution(cfg_path)
    if path is not None:
        try:
            data = _find(data, path)
        except (KeyError, TypeError):
            return default
    if as_bool:
        return (
            isinstance(data, str) and data.strip().lower() in ("1", "true")
        ) or data is True
    return data
