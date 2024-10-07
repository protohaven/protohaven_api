"""Test of fowarding CLI commands"""
from collections import namedtuple

import pytest
import yaml

from protohaven_api.commands import forwarding as F
from protohaven_api.testing import MatchStr, d, idfn, mkcli, t


@pytest.fixture
def cli(capsys):
    return mkcli(capsys, F)


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
def test_tech_sign_ins(mocker, tc, cli):
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
    got = cli("tech_sign_ins", ["--now", tc.now.isoformat()])
    assert len(got) == (1 if len(tc.want) > 0 else 0)
    for w in tc.want:
        assert w in got[0]["body"]


def test_project_requests(mocker, cli):
    mocker.patch.object(
        F.tasks,
        "get_project_requests",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
                "notes": f"Project Description:\\nTest Desc\\nMaterials Budget: $5\\nDeadline for Project Completion:\\n{d(1).isoformat()}\\n",
            }
        ],
    )
    mocker.patch.object(F, "tznow", return_value=d(0))
    mocker.patch.object(F.tasks, "complete")
    assert cli("project_requests", ["--apply"]) == [
        {
            "body": MatchStr("Test Desc"),
            "subject": MatchStr("Project Request"),
            "target": "#help-wanted",
        }
    ]
    F.tasks.complete.assert_called_with("123")


def test_shop_tech_applications(mocker, cli):
    mocker.patch.object(
        F.tasks,
        "get_shop_tech_applicants",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
            }
        ],
    )
    assert cli("shop_tech_applications", []) == [
        {
            "body": MatchStr("Foo"),
            "subject": MatchStr("shop tech"),
            "target": "#tech-leads",
        }
    ]


def test_instructor_applications(mocker, cli):
    mocker.patch.object(
        F.tasks,
        "get_instructor_applicants",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
            }
        ],
    )
    assert cli("instructor_applications", []) == [
        {
            "body": MatchStr("Foo"),
            "subject": MatchStr("instructor"),
            "target": "#education-leads",
        }
    ]


def test_class_proposals(mocker, cli):
    mocker.patch.object(
        F.airtable,
        "get_all_class_templates",
        return_value=[
            {
                "fields": {"Name": "Test Class"},
            }
        ],
    )
    assert cli("class_proposals", []) == [
        {
            "body": MatchStr("Test Class"),
            "subject": MatchStr("class"),
            "target": "#education-leads",
        }
    ]


def test_private_instruction_email(mocker, cli):
    mocker.patch.object(
        F.tasks,
        "get_private_instruction_requests",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
                "created_at": d(0).isoformat(),
                "notes": "Name:\nFoo\nDetails:\ntest details\nAvailability:\nwhenever\nEmail:\na@b.com\n———————Footer to ignore",
            }
        ],
    )
    mocker.patch.object(F, "tznow", return_value=d(0))
    assert cli("private_instruction", []) == [
        {
            "body": MatchStr("Foo"),
            "subject": MatchStr("Private Instruction"),
            "target": t,
        }
        for t in ("membership@protohaven.org", "#education-leads")
    ]


def test_private_instruction_daily(mocker, cli):
    mocker.patch.object(
        F.tasks,
        "get_private_instruction_requests",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
                "created_at": d(0).isoformat(),
                "notes": "Name:\nFoo\nDetails:\ntest details\nAvailability:\nwhenever\nEmail:\na@b.com\n———————Footer to ignore",
            }
        ],
    )
    mocker.patch.object(F, "tznow", return_value=d(0))
    assert cli("private_instruction", ["--daily"]) == [
        {
            "body": MatchStr("Foo"),
            "subject": MatchStr("Private Instruction"),
            "target": "#private-instructors",
        }
    ]


def test_phone_messages(mocker, cli):
    mocker.patch.object(
        F.tasks,
        "get_phone_messages",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
                "created_at": d(0).isoformat(),
                "notes": "test notes",
            }
        ],
    )
    mocker.patch.object(F.tasks, "complete")
    assert cli("phone_messages", ["--apply"]) == [
        {
            "body": MatchStr("test notes"),
            "subject": MatchStr("phone message"),
            "target": "hello@protohaven.org",
        }
    ]
    F.tasks.complete.assert_called_with("123")


def test_purchase_request_alerts(mocker, cli):
    mocker.patch.object(
        F.tasks,
        "get_open_purchase_requests",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
                "created_at": d(0),
                "modified_at": d(0),
                "category": "high_pri",
                "notes": "test notes",
            }
        ],
    )
    mocker.patch.object(F, "tznow", return_value=d(14))
    mocker.patch.object(F.tasks, "complete")
    mocker.patch.object(F.comms, "send_board_message")
    cli("purchase_request_alerts", [])
    F.comms.send_board_message.assert_called_with(MatchStr("Foo"))
