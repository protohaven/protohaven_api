"""Helpers for testing code"""

import datetime
import re

import pytest
import yaml

from protohaven_api.app import configure_app
from protohaven_api.config import tz
from protohaven_api.integrations.cronicle import Progress


class MatchStr:  # pylint: disable=too-few-public-methods
    """Matchstr("foo") == "asdf foo bar", etc."""

    def __init__(self, r):
        self.r = r

    def __eq__(self, other):
        """Check for equality - true if string matches regex"""
        return re.search(self.r, other) is not None


def d(i, h=0):
    """Returns a date based on an integer, for testing"""
    return datetime.datetime(year=2025, month=1, day=1, tzinfo=tz) + datetime.timedelta(
        days=i, hours=h
    )


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
        getattr(module.Commands(), cmd)(args, Progress())
        captured = capsys.readouterr()
        return yaml.safe_load(captured.out) if parse_yaml else captured.out.strip()

    return run


@pytest.fixture(name="client")
def fixture_client():
    """Provide a test client for making requests"""
    return configure_app(
        session_secret="asdf"  # pragma: allowlist secret
    ).test_client()


def setup_session(client, roles=True):
    """Add session details to client fixture"""
    with client.session_transaction() as session:
        session["neon_id"] = 1234

        acf = [
            {
                "name": "Clearances",
                "optionValues": [{"name": "C1"}, {"name": "C2"}],
            },
        ]
        # It's important to support setting roles to [], None (not listed in custom fields),
        # and a default value. This is why we use `True` as the signal here to apply defaults
        if roles is not None:
            acf.append(
                {
                    "name": "API server role",
                    "optionValues": (
                        [{"name": "Board Member"}] if roles is True else roles
                    ),
                }
            )

        session["neon_account"] = {
            "individualAccount": {
                "accountId": 1234,
                "accountCustomFields": acf,
                "primaryContact": {
                    "firstName": "First",
                    "lastName": "Last",
                    "email1": "foo@bar.com",
                },
            }
        }
