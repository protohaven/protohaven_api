## Reading GitHub issues

Use the GitHub REST API to read issue links provided by the user

## Environment setup

Before starting, create a venv and `pip install -r requirements.txt` to pull python dependencies.

Also `pip install pre-commit` to prepare for post-development steps.

## Python Unit Testing

* Prefer `mocker.patch.object` over `mocker.patch`
* Do not mock: logging functions, `tz` (the timezone object), `dateparser`
* Mocking `tznow` (the current time function) is acceptable when tests need to control time
* When providing test datetime objects, use the builtin `d()` and `t()` functions defined in `protohaven_api/testing.py`
* If `return_value` is needed for a mock, define it as part of the call to `mocker.patch.object`.


For functions decorated with `@command` that use `print_yaml`, create a use-case specific CLI for the module that handles the yaml parsing automatically:

```
from protohaven_api.commands import <thismodule> as C
from protohaven_api.testing import mkcli
@pytest.fixture(name="cli")
def fixture_cli(capsys):
    return mkcli(capsys, C)

def test_foo(cli):
    ...
    cli("cli_command", ["--arguments", "--here"])
```

## Post-Development

Please remember to run pre-commit to autoformat all files, detect and remove linter errors etc.

If you modified python code, run pytest.
