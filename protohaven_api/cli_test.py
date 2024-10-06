"""Tests for CLI commands"""
# pylint: skip-file
import sys
import tempfile

import pytest

from protohaven_api.cli import ProtohavenCLI
from protohaven_api.commands.decorator import dump_yaml, is_command
from protohaven_api.integrations.data.connector import get as get_connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.integrations.data.dev_connector import DevConnector

OK_FNS = []


class EnvBase:
    args = []
    want = "[]"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class TmpfileEnv(EnvBase):
    def __enter__(self):
        self.f = tempfile.NamedTemporaryFile()
        self.f.write(
            bytes(
                dump_yaml(
                    [
                        {
                            "target": "a@b.com",
                            "subject": "Test Subject",
                            "body": "Test Body",
                        }
                    ]
                ),
                encoding="utf8",
            )
        )
        self.f.flush()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.f.close()


class EnvSendComms(TmpfileEnv):
    def __enter__(self):
        super.__enter__()
        self.args = ["--path", self.f.name, "--confirm"]
        return self


class EnvAppendSchedule(TmpfileEnv):
    def __enter__(self):
        super().__enter__()
        self.args = ["--path", self.f.name]
        return self


class EnvValidateMemberships(EnvBase):
    pass


class EnvBuildSchedulerEnv(EnvBase):
    pass


class EnvCancelClasses(EnvBase):
    pass


class EnvClassProposals(EnvBase):
    pass


class EnvEnforceDiscordNicknames(EnvBase):
    pass


class EnvEnforcePolicies(EnvBase):
    pass


class EnvGenClassEmails(EnvBase):
    pass


class EnvGenInstructorScheduleReminder(EnvBase):
    pass


class EnvGenMaintenanceTasks(EnvBase):
    pass


class EnvGenMockData(EnvBase):
    pass


class EnvGenTechLeadsMaintenanceSummary(EnvBase):
    pass


class EnvInitNewMemberships(EnvBase):
    pass


class EnvInstructorApplications(EnvBase):
    pass


class EnvPhoneMessages(EnvBase):
    pass


class EnvPostClassesToNeon(EnvBase):
    pass


class EnvPrivateInstruction(EnvBase):
    pass


class EnvProjectRequests(EnvBase):
    pass


class EnvPurchaseRequestAlerts(EnvBase):
    pass


class EnvReserveEquipmentForClass(EnvBase):
    pass


class EnvReserveEquipmentFromTemplate(EnvBase):
    pass


class EnvRunScheduler(EnvBase):
    pass


class EnvShopTechApplications(EnvBase):
    pass


class EnvSyncReservableTools(EnvBase):
    pass


class EnvTechSignIns(EnvBase):
    pass


class EnvTransactionAlerts(EnvBase):
    pass


class EnvUpdateRoleIntents(EnvBase):
    pass


class EnvValidateDocs(EnvBase):
    pass


def get_env(cmd):
    """Convert cmd to CamelCase and return the object with that name"""
    ename = "Env" + "".join(word.title() for word in cmd.split("_"))
    ecls = globals().get(ename, None)
    if not ecls:
        raise RuntimeError(f"Missing env class {ename} for testing command {cmd}")
    return ecls()


@pytest.fixture
def cli(mocker, capsys):
    init_connector(DevConnector)

    def do_cli_readonly(args):
        mocker.patch.object(sys, "argv", args)
        ProtohavenCLI()
        captured = capsys.readouterr()
        return captured.out.strip()

    return do_cli_readonly


@pytest.mark.parametrize(
    "cmd",
    [cmd for cmd in dir(ProtohavenCLI) if is_command(getattr(ProtohavenCLI, cmd))],
)
def test_cli_commands_no_apply_no_function_calls(cli, cmd):
    """Runs each cli method with --apply and ensures
    no modifications are made. This implicitly also
    requires commands to all have --applyflags."""
    conn = get_connector()
    with get_env(cmd) as env:
        out = cli(["/asdf/ghjk", cmd, "--no-apply", *env.args])
        assert out == env.want
        assert not conn.mutated and not conn.sent_comms
