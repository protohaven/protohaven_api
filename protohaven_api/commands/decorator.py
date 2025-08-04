"""Basic decorator for argparse commands that wraps functions so they can be executed in cli."""

import argparse
import functools
import logging
from typing import Any, Callable, Dict, Tuple

import yaml

from protohaven_api.config import get_config

log = logging.getLogger("decorator")


def command(*parser_args: Tuple[str, Dict[str, Any]]) -> Callable:
    """Returns a configured decorator that provides help info based on the function comment
    and parses all args given to the function"""

    def decorate(func: Callable) -> Callable:
        """Sets up help doc and parses all args"""

        @functools.wraps(func)
        def wrapper(*args: Any) -> Any:
            parser = argparse.ArgumentParser(description=func.__doc__)
            for cmd, pkwarg in parser_args:
                parser.add_argument(cmd, **pkwarg)
            parsed_args = parser.parse_args(args[1])  # argv
            return func(args[0], parsed_args, *args[2:])

        wrapper.is_command = True  # type: ignore[attr-defined]
        return wrapper

    return decorate


def is_command(func: Callable) -> bool:
    """Check if @command is applied to a given method."""
    return hasattr(func, "is_command")


def arg(*args: str, **kwargs: Any) -> Tuple[str, Dict[str, Any]]:
    """Allows specifying of arguments in a parser.Argument call, but instead via decorato"""
    assert len(args) == 1
    return args[0], kwargs


def load_yaml(path: str) -> Any:
    """Loads yaml file from a path"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f.read())


def dump_yaml(data: Any) -> str:
    """Dumps yaml to string"""
    if not isinstance(data, list):
        data = [data]
    data = [dict(d) for d in data]
    return yaml.dump(data, default_flow_style=False, default_style="")


def print_yaml(data: Any) -> None:
    """Prints yaml to config defined path, or to stdout if not set"""
    path = get_config("general/yaml_out").strip()
    if path and path != "${YAML_OUT}":
        log.info(f"Writing yaml file to '{path}'")
        with open(path, "w", encoding="utf8") as f:
            f.write(dump_yaml(data))
    else:
        print(dump_yaml(data))
