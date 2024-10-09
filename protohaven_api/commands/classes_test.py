"""Test for class command logic"""
# pylint: skip-file
import datetime
from collections import namedtuple
from unittest.mock import call

import pytest

from protohaven_api.commands import classes as C
from protohaven_api.integrations import neon
from protohaven_api.testing import Any, d, idfn, mkcli


def test_category_from_event_name():
    """Test a few cases to make sure categories are correctly applied"""
    assert (
        C.Commands._neon_category_from_event_name("Digital 113: 2D Vector Creation")
        == neon.Category.PROJECT_BASED_WORKSHOP
    )
    assert (
        C.Commands._neon_category_from_event_name("Welding 101: MIG Welding Clearance")
        == neon.Category.SKILLS_AND_SAFETY_WORKSHOP
    )
    assert (
        C.Commands._neon_category_from_event_name("All Member Meeting")
        == neon.Category.MEMBER_EVENT
    )
    assert (
        C.Commands._neon_category_from_event_name("Valentine's Day Make & Take Party")
        == neon.Category.SOMETHING_ELSE_AMAZING
    )


@pytest.fixture
def e(mocker):
    mocker.patch.object(C.airtable, "update_record")
    mocker.patch.object(C.neon, "set_event_scheduled_state")
    mocker.patch.object(C.neon, "assign_pricing")
    mocker.patch.object(C.neon, "create_event")
    mocker.patch.object(C.scheduler, "push_schedule")
    return C


@pytest.fixture
def cli(capsys):
    return mkcli(capsys, C)


# Compatible with print_yaml() function
TESTVAL = [{"a": "b"}]


def test_gen_instructor_schedule_reminder(mocker, cli):
    mocker.patch.object(C.builder, "gen_scheduling_reminders", return_value=TESTVAL)
    assert (
        cli(
            "gen_instructor_schedule_reminder",
            ["--start", d(0).isoformat(), "--end", d(1).isoformat()],
        )
        == TESTVAL
    )
    C.builder.gen_scheduling_reminders.assert_called_with(d(0), d(1))


def test_gen_class_emails(cli, mocker):
    eb = mocker.patch.object(C.builder.ClassEmailBuilder, "build", return_value=TESTVAL)
    assert cli("gen_class_emails", []) == TESTVAL


def test_build_scheduler_env(cli, mocker):
    mocker.patch.object(C.scheduler, "generate_env", return_value=TESTVAL)
    assert (
        cli(
            "build_scheduler_env",
            ["--start", d(0).isoformat(), "--end", d(1).isoformat(), "--filter", "foo"],
        )
        == TESTVAL
    )
    C.scheduler.generate_env.assert_called_with(d(0), d(1), set(["foo"]))


@pytest.fixture
def tfile(tmp_path):
    f = tmp_path / "tmp.txt"
    f.write_text('- "test"')
    return str(f)


def test_run_scheduler(cli, mocker, tfile):
    eb = mocker.patch.object(
        C.scheduler, "solve_with_env", return_value=(TESTVAL, None)
    )
    assert cli("run_scheduler", ["--path", tfile]) == TESTVAL
    C.scheduler.solve_with_env.assert_called_with("test")


def test_append_schedule_no_apply(cli, mocker, tfile):
    eb = mocker.patch.object(
        C.scheduler, "gen_schedule_push_notifications", return_value=TESTVAL
    )
    eb = mocker.patch.object(C.scheduler, "push_schedule")
    assert cli("append_schedule", ["--path", str(tfile)]) == TESTVAL
    C.scheduler.push_schedule.assert_not_called()


def test_append_schedule_apply(cli, mocker, tfile):
    eb = mocker.patch.object(
        C.scheduler, "gen_schedule_push_notifications", return_value=TESTVAL
    )
    eb = mocker.patch.object(C.scheduler, "push_schedule")
    assert cli("append_schedule", ["--path", str(tfile), "--apply"]) == TESTVAL
    C.scheduler.push_schedule.assert_called_with("test")


def test_cancel_classes(cli, mocker):
    eb = mocker.patch.object(C.neon, "set_event_scheduled_state")
    cli("cancel_classes", ["--id", "1", "2"])
    C.neon.set_event_scheduled_state.assert_has_calls(
        [call("1", scheduled=False), call("2", scheduled=False)]
    )


def tcls(start=d(30).isoformat(), confirmed=d(0).isoformat(), neon_id=""):
    return {
        "id": "abcd",
        "fields": {
            "ID": "123",
            "Start Time": start,
            "Name (from Class)": ["Test Class"],
            "Neon ID": neon_id,
            "Confirmed": confirmed,
            "Instructor": "inst1",
            "Short Description (from Class)": ["testdesc"],
            "Hours (from Class)": [3],
            "Days (from Class)": [1],
            "Capacity (from Class)": [6],
            "Price (from Class)": [90],
            "Name (from Area) (from Class)": [90],
            "Email": "a@b.com",
        },
    }


Tc = namedtuple("Tc", "desc,cls")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("No classes", []),
        Tc("Too soon in future", [tcls(start=d(13).isoformat())]),
        Tc("Unconfirmed", [tcls(confirmed=None)]),
        Tc("Already scheduled", [tcls(neon_id="1234")]),
    ],
    ids=idfn,
)
def test_post_classes_to_neon_no_actions(cli, mocker, tc):
    """Test cases where the scheduling action is skipped"""
    mocker.patch.object(
        C.neon,
        "_schedule_event",
        create=True,
        side_effect=RuntimeError("Should not have scheduled"),
    )
    mocker.patch.object(
        C.airtable, "get_class_automation_schedule", return_value=tc.cls
    )
    mocker.patch.object(C, "tznow", return_value=d(0))
    assert cli("post_classes_to_neon", ["--apply"]) == []


Tc = namedtuple("Tc", "desc,args,publish,register,discount")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("defaults", [], True, True, True),
        Tc("no publish", ["--no-publish"], False, True, True),
        Tc("no registration", ["--no-registration"], True, False, True),
        Tc("no discounts", ["--no-discounts"], True, True, False),
    ],
    ids=idfn,
)
def test_post_classes_to_neon_actions(cli, mocker, tc):
    """Test cases where the class is scheduled, with various args applied"""
    mocker.patch.object(C.neon, "assign_pricing")
    mocker.patch.object(C.neon, "create_event", return_value="123")
    mocker.patch.object(C.airtable, "update_record")
    mocker.patch.object(
        C.Commands, "_reserve_equipment_for_class_internal", create=True
    )
    mocker.patch.object(
        C.airtable, "get_class_automation_schedule", return_value=[tcls()]
    )
    mocker.patch.object(C, "tznow", return_value=d(0))
    mocker.patch.object(
        C.Commands, "_fetch_boilerplate", return_value=("Foo", "Bar", "Baz")
    )
    got = cli("post_classes_to_neon", ["--apply", *tc.args])

    assert {g["target"] for g in got} == {
        "a@b.com",
        "#instructors",
        "#class-automation",
    }
    C.neon.create_event.assert_called_with(
        Any(),
        Any(),
        d(30),
        d(30) + datetime.timedelta(hours=3),
        category="27",
        max_attendees=6,
        dry_run=False,
        published=tc.publish,
        registration=tc.register,
    )
    C.neon.create_event.mock_calls[0][0] == "Test Class"
    C.neon.assign_pricing.assert_called_with(
        "123", 90, 6, include_discounts=tc.discount, clear_existing=True
    )
    assert C.Commands._reserve_equipment_for_class_internal.call_args.args[0]["123"]
    assert C.Commands._reserve_equipment_for_class_internal.call_args[0][1] == True
