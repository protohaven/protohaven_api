"""Test of fowarding CLI commands"""
import yaml

from protohaven_api.commands import forwarding as F
from protohaven_api.testing import t


def test_tech_sign_ins_am_shift_bad(mocker, capsys):
    """Notifies if nobody is signed in for the AM shift"""
    mocker.patch.object(F.sheets, "get_sign_ins_between", return_value=[])
    mocker.patch.object(
        F.neon,
        "fetch_techs_list",
        return_value=[
            {"email": "a@b.com", "name": "A B", "shift": "Monday AM"},
        ],
    )
    F.Commands().tech_sign_ins(["--now", t(11, 0).isoformat()])

    got = yaml.safe_load(capsys.readouterr().out.strip())
    assert len(got) == 1
    assert "a@b.com" in got[0]["body"]
    assert "no techs assigned for Monday AM" in got[0]["body"]
