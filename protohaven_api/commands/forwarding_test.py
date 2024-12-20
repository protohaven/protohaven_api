"""Test of fowarding CLI commands"""

from collections import namedtuple

import pytest

from protohaven_api.commands import forwarding as F
from protohaven_api.testing import MatchStr, d, idfn, mkcli, t


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create cli() test function"""
    return mkcli(capsys, F)


# Note: space and weird capitalizations here stress test the email matching
# since both the tech emails (from Neon) and the sign ins (from Sheets) are
# user inputs and can be arbitrarily cased, while emails are case-insensitive.
AM_TECH = {"email": "  a@b.CoM", "name": "A B", "shift": "Monday AM"}
PM_TECH = {"email": "c@d.CoM  ", "name": "C D", "shift": "Monday PM"}

Tc = namedtuple("TC", "desc,now,signins,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc(
            "AM shift without signin",
            t(11, 0),
            [],
            [AM_TECH["email"].strip().lower(), "no techs assigned for Monday AM"],
        ),
        Tc("AM shift with signin", t(11, 0), [AM_TECH], []),
        Tc(
            "PM shift without signin",
            t(17, 0),
            [],
            [PM_TECH["email"].strip().lower(), "no techs assigned for Monday PM"],
        ),
        Tc("PM shift with signin", t(17, 0), [PM_TECH], []),
        Tc("No techs", t(11, 0), [], ["no techs assigned"]),
        Tc("Case & space insensitive", t(17, 0), [{"email": "   C@D.COM    "}], []),
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
                {
                    "AM": {"people": [AM_TECH["name"]]},
                    "PM": {"people": [PM_TECH["name"]]},
                }
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
    """Test behavior of the `project_requests` CLI command"""
    mocker.patch.object(
        F.tasks,
        "get_project_requests",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
                "notes": (
                    f"Project Description:\\nTest Desc\\nMaterials Budget: $5\\n"
                    f"Deadline for Project Completion:\\n{d(1).isoformat()}\\n"
                ),
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
    F.tasks.complete.assert_called_with("123")  # pylint: disable=no-member


def test_shop_tech_applications(mocker, cli):
    """Test `shop_tech_applications` cmd"""
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
    """Test `instructor_applications` cmd"""
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
    """Test `class_proposals` cmd"""
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
    """Test `private_instruction` sends to email"""
    mocker.patch.object(
        F.tasks,
        "get_private_instruction_requests",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
                "created_at": d(0).isoformat(),
                "notes": (
                    "Name:\nFoo\nDetails:\ntest details\nAvailability:"
                    "\nwhenever\nEmail:\na@b.com\n———————Footer to ignore"
                ),
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
    """Test daily run of private instruction sends to discord"""
    mocker.patch.object(
        F.tasks,
        "get_private_instruction_requests",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
                "created_at": d(0).isoformat(),
                "notes": (
                    "Name:\nFoo\nDetails:\ntest details\nAvailability:\nwhenever\n"
                    "Email:\na@b.com\n———————Footer to ignore"
                ),
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
    """Test `phone_messages` cli command"""
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
    mocker.patch.object(F.tasks, "complete", return_value=None)
    assert cli("phone_messages", ["--apply"]) == [
        {
            "body": MatchStr("test notes"),
            "subject": MatchStr("phone message"),
            "target": "hello@protohaven.org",
        }
    ]
    F.tasks.complete.assert_called_with("123")  # pylint: disable=no-member


def test_purchase_request_alerts(mocker, cli):
    """Test `purchase_request_alerts` cli command"""
    mocker.patch.object(
        F.tasks,
        "get_open_purchase_requests",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
                "created_at": d(0),
                "modified_at": d(0),
                "category": "requested",
                "notes": "test notes",
            }
        ],
    )
    mocker.patch.object(F, "tznow", return_value=d(30))
    assert cli("purchase_request_alerts", []) == [
        {
            "subject": MatchStr("Open purchase requests"),
            "body": MatchStr("1 total"),
            "target": "#finance-automation",
        }
    ]
