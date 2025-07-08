"""Test of fowarding CLI commands"""

from collections import namedtuple

import pytest

from protohaven_api.commands import forwarding as F
from protohaven_api.testing import MatchStr, d, idfn, mkcli, t


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    """Create cli() test function"""
    return mkcli(capsys, F)


Tc = namedtuple("TC", "desc,now,signins,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc(
            "AM shift without signin",
            t(11, 0),
            [],
            ["a@b.com", "no techs assigned for Monday AM"],
        ),
        Tc("AM shift with signin", t(11, 0), ["a@b.com"], []),
        Tc(
            "PM shift without signin",
            t(17, 0),
            [],
            ["c@d.com", "no techs assigned for Monday PM"],
        ),
        Tc("PM shift with signin", t(17, 0), ["c@d.com"], []),
        Tc("No techs", t(11, 0), [], ["no techs assigned"]),
    ],
    ids=idfn,
)
def test_tech_sign_ins(mocker, tc, cli):
    """Notifies if nobody is signed in for the AM shift"""
    # Note: we're mocking a Member class object, where the email values
    # are stripped and lowercased for consistent matching

    mocker.patch.object(
        F.airtable,
        "get_signins_between",
        return_value=[mocker.MagicMock(email=s) for s in tc.signins],
    )
    mocker.patch.object(
        F.forecast,
        "generate",
        return_value={
            "calendar_view": [
                {
                    "AM": {
                        "people": [
                            mocker.Mock(
                                email="a@b.com",
                                name="A B (they/them)",
                                shift=["Monday", "AM"],
                            )
                        ]
                    },
                    "PM": {
                        "people": [
                            mocker.Mock(
                                email="c@d.com",
                                name="C D (he/him)",
                                shift=["Monday", "PM"],
                            )
                        ]
                    },
                }
            ]
        },
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
    got = cli("shop_tech_applications", [])[0]
    assert got["target"] == "#tech-automation"
    assert got["subject"] == MatchStr("shop tech")


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
    got = cli("instructor_applications", [])[0]
    assert got["subject"] == MatchStr("instructor")
    assert got["target"] == "#edu-automation"


def test_private_instruction_email(mocker, cli):
    """Test `private_instruction` sends to email"""
    avail = "".join(["whenever"] * 100)
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
                    f"\n{avail}\nEmail:\na@b.com\n———————Footer to ignore"
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
        for t in ("membership@protohaven.org", "#edu-automation")
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


def test_donation_requests(mocker, cli):
    """Test `donation_requests` cli command"""
    mocker.patch.object(
        F.tasks,
        "get_donation_requests",
        return_value=[
            {
                "gid": "123",
                "name": "Foo",
            }
        ],
    )
    assert cli("donation_requests", []) == [
        {
            "subject": MatchStr("donation"),
            "body": MatchStr("- Foo"),
            "target": "#donation-automation",
        }
    ]


def test_supply_requests(mocker, cli):
    """Test `supply_requests` cli command"""
    mocker.patch.object(F, "tznow", return_value=d(0))
    mocker.patch.object(
        F.airtable,
        "get_class_automation_schedule",
        return_value=[
            {"fields": f}
            for f in [
                {
                    # Confirmed, so not listed
                    "Supply State": "Supplies Confirmed",
                    "Start Time": d(1).isoformat(),
                },
                {
                    # Already happened, so not listed
                    "Supply State": "Supplies Requested",
                    "Start Time": d(-1).isoformat(),
                },
                {
                    "Supply State": "Supplies Requested",
                    "Start Time": d(1).isoformat(),
                    "Instructor": "Inst",
                    "Name (from Class)": ["Classname"],
                },
            ]
        ],
    )
    assert cli("supply_requests", []) == [
        {
            "subject": "1 class(es) still need supplies:",
            "body": "- in 1 day(s): Classname by Inst on 2025-01-02",
            "target": "#supply-automation",
        }
    ]
