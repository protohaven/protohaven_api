"""Loads config.yaml"""
import yaml

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)


def get_config():
    """Fetches the config"""
    return cfg
