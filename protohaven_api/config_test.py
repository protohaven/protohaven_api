# pylint: skip-file
import datetime

import pytest

from protohaven_api import config as c


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
    if (
        c.get_config(*[a.replace("'", "").replace('"', "") for a in args], **kwargs)
        is None
    ):
        raise AssertionError(f"get_config(*{args}, **{kwargs}) is None")


def test_safe_parse_datetime_naive():
    """Test safe_parse_datetime with timezone-naive strings"""
    # Test naive datetime string - should be interpreted as Eastern time
    result = c.safe_parse_datetime("2025-01-01 18:00:00")
    expected = datetime.datetime(2025, 1, 1, 18, 0, 0, tzinfo=c.tz)
    assert result == expected
    assert result.tzinfo == c.tz

    # Test date-only string
    result = c.safe_parse_datetime("2025-01-01")
    expected = datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=c.tz)
    assert result == expected
    assert result.tzinfo == c.tz


def test_safe_parse_datetime_aware():
    """Test safe_parse_datetime with timezone-aware strings"""
    # Test UTC datetime string - should be converted to Eastern
    result = c.safe_parse_datetime("2025-01-01T18:00:00Z")
    expected = datetime.datetime(
        2025, 1, 1, 13, 0, 0, tzinfo=c.tz
    )  # 18:00 UTC = 13:00 EST
    assert result == expected
    assert result.tzinfo == c.tz

    # Test datetime with explicit timezone
    result = c.safe_parse_datetime("2025-01-01T18:00:00-05:00")
    expected = datetime.datetime(2025, 1, 1, 18, 0, 0, tzinfo=c.tz)
    assert result == expected
    assert result.tzinfo == c.tz


def test_safe_parse_datetime_dst_boundary():
    """Test safe_parse_datetime across DST boundaries"""
    # Before DST (EST)
    result = c.safe_parse_datetime("2025-01-01 18:00:00")
    assert result.strftime("%z") == "-0500"  # EST

    # After DST transition (EDT)
    result = c.safe_parse_datetime("2025-07-01 18:00:00")
    assert result.strftime("%z") == "-0400"  # EDT
