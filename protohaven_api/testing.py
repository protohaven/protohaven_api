"""Helpers for testing code"""

import datetime
import re

import yaml

from protohaven_api.config import tz


class Any:  # pylint: disable=too-few-public-methods
    """Matches any value - used for placeholder matching in asserts"""

    def __eq__(self, other):
        """Check for equality - always true"""
        return True


class MatchStr:  # pylint: disable=too-few-public-methods
    """Matchstr("foo") == "asdf foo bar", etc."""

    def __init__(self, r):
        self.r = r

    def __eq__(self, other):
        """Check for equality - true if string matches regex"""
        return re.search(self.r, other) is not None


def d(i, h=0):
    """Returns a date based on an integer, for testing"""
    return (
        datetime.datetime(year=2025, month=1, day=1)
        + datetime.timedelta(days=i, hours=h)
    ).astimezone(tz)


def t(hour, weekday=0):
    """Create a datetime object from hour and weekday"""
    return datetime.datetime(
        year=2024,
        month=11,
        day=4 + weekday,
        hour=hour,
        minute=0,
        second=0,
        tzinfo=tz,
    )


def idfn(tc):
    """Extract description from named tuple for parameterization"""
    return tc.desc


def mkcli(capsys, module):
    """Invoke CLI, read stdout, and return yaml-ized result text."""

    def run(cmd: str, args: list, parse_yaml=True):
        getattr(module.Commands(), cmd)(args)
        captured = capsys.readouterr()
        return yaml.safe_load(captured.out) if parse_yaml else captured.out.strip()

    return run
