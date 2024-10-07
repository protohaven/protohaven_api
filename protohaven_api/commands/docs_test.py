import pytest

from protohaven_api.commands import docs as d
from protohaven_api.testing import mkcli


@pytest.fixture
def cli(capsys):
    return mkcli(capsys, d)


def test_validate_docs(cli, mocker):
    mocker.patch.object(d, "validate_docs", return_value={"a": "b"})
    assert cli("validate_docs", []) == [{"a": "b"}]
