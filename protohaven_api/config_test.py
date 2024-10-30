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


def search_config_calls():
    import ast
    import os

    calls = []
    for root, _, files in os.walk("protohaven_api"):
        for file in files:
            if file.endswith(".py"):
                with open(os.path.join(root, file), "r") as f:
                    node = ast.parse(f.read(), filename=file)
                    for n in ast.walk(node):
                        if (
                            isinstance(n, ast.Call)
                            and isinstance(n.func, ast.Name)
                            and n.func.id == "get_config"
                        ):
                            args = [ast.unparse(arg) for arg in n.args]
                            kwargs = {
                                kw.arg: ast.unparse(kw.value) for kw in n.keywords
                            }
                            calls.append((args, kwargs))
    return calls


@pytest.mark.parametrize("args,kwargs", search_config_calls())
def test_config_references(args, kwargs):
    assert len(args) > 0
    assert (
        c.get_config(*[a.replace("'", "").replace('"', "") for a in args], **kwargs)
        is not None
    )
