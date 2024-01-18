"""Loads config.yaml"""
from functools import cache

import yaml


@cache
def get_config():
    """Fetches the config"""
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg
