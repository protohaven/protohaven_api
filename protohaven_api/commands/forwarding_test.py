"""Test of fowarding CLI commands"""
from collections import namedtuple

import pytest
import yaml

from protohaven_api.commands import forwarding as F
from protohaven_api.testing import idfn, t

AM_TECH = {"email": "a@b.com", "name": "A B", "shift": "Monday AM"}
PM_TECH = {"email": "c@d.com", "name": "C D", "shift": "Monday PM"}

Tc = namedtuple("TC", "desc,now,signins,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc(
            "AM shift without signin",
            t(11, 0),
            [],
            [AM_TECH["email"], "no techs assigned for Monday AM"],
        ),
        Tc("AM shift with signin", t(11, 0), [AM_TECH], []),
        Tc(
            "PM shift without signin",
            t(17, 0),
            [],
            [PM_TECH["email"], "no techs assigned for Monday PM"],
        ),
        Tc("PM shift with signin", t(17, 0), [PM_TECH], []),
        Tc("No techs", t(11, 0), [], ["no techs assigned"]),
    ],
    ids=idfn,
)
def test_tech_sign_ins(mocker, capsys, tc):
    """Notifies if nobody is signed in for the AM shift"""
    mocker.patch.object(F.sheets, "get_sign_ins_between", return_value=tc.signins)
    mocker.patch.object(
        F.forecast,
        "generate",
        return_value={
            "calendar_view": [
                [{"people": [AM_TECH["name"]]}, {"people": [PM_TECH["name"]]}]
            ]
        },
    )
    mocker.patch.object(
        F.neon,
        "fetch_techs_list",
        return_value=[AM_TECH, PM_TECH],
    )
    F.Commands().tech_sign_ins(["--now", tc.now.isoformat()])

    got = yaml.safe_load(capsys.readouterr().out.strip())
    assert len(got) == (1 if len(tc.want) > 0 else 0)
    for w in tc.want:
        assert w in got[0]["body"]
