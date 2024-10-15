# pylint: skip-file
import pytest

from protohaven_api import config as c


def test_exec_details_footer(mocker):
    mocker.patch.object(c, "get_execution_log_link", return_value="TEST_LINK")
    assert "TEST_LINK" in c.exec_details_footer()


def test_exec_details_footer_empty(mocker):
    mocker.patch.object(c, "get_execution_log_link", return_value=None)
    assert c.exec_details_footer() == ""


@pytest.mark.parametrize(
    "data,path,default,want",
    [
        ({}, None, None, {}),
        ({"a": 1}, None, None, {"a": 1}),
        ({"a": 1}, "a", None, 1),
        ({"a": 1}, "a/b", 2, 2),
        ({"a": {"b": 1}}, "a/b", None, 1),
        ({"a": {"b": 1}}, "a", None, {"b": 1}),
    ],
)
def test_get_config(data, path, default, want, mocker):
    mocker.patch.object(c, "load_yaml_with_env_substitution", return_value=data)
    assert c.get_config(path, default) == want
