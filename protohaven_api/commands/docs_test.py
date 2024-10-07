"""Test methods for documentation CLI commands"""

import pytest

from protohaven_api.commands import docs as d
from protohaven_api.testing import mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Generate cli function for testing"""
    return mkcli(capsys, d)


def test_validate_docs(cli, mocker):
    """Try running `validate_docs`, and ensure output is printed"""
    mocker.patch.object(d, "validate_docs", return_value={"a": "b"})
    assert cli("validate_docs", []) == [{"a": "b"}]
