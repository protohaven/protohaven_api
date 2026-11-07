"""Tests for command decorators and yaml helpers."""

from protohaven_api.commands import decorator


def test_print_yaml_handles_missing_yaml_out_config(capsys, mocker):
    """print_yaml should fall back to stdout when yaml_out config is unset."""
    mocker.patch.object(decorator, "get_config", return_value=None)
    decorator.print_yaml([])
    assert capsys.readouterr().out == "[]\n\n"
