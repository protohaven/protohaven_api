"""Test for class command logic"""

# pylint: skip-file
import datetime
from collections import namedtuple

import pytest

from protohaven_api.commands import classes as C
from protohaven_api.integrations.data.neon import Category
from protohaven_api.testing import MatchStr, d, idfn, mkcli


def test_category_from_event_name():
    """Test a few cases to make sure categories are correctly applied"""
    assert (
        C.Commands._neon_category_from_event_name("Digital 113: 2D Vector Creation")
        == Category.PROJECT_BASED_WORKSHOP
    )
    assert (
        C.Commands._neon_category_from_event_name("Welding 101: MIG Welding Clearance")
        == Category.SKILLS_AND_SAFETY_WORKSHOP
    )
    assert (
        C.Commands._neon_category_from_event_name("All Member Meeting")
        == Category.MEMBER_EVENT
    )
    assert (
        C.Commands._neon_category_from_event_name("Valentine's Day Make & Take Party")
        == Category.SOMETHING_ELSE_AMAZING
    )


@pytest.fixture(name="e")
def fixture_e(mocker):
    mocker.patch.object(C.airtable, "update_record")
    mocker.patch.object(C.neon, "set_event_scheduled_state")
    mocker.patch.object(C.neon, "assign_pricing")
    mocker.patch.object(C.neon, "create_event")
    mocker.patch.object(C.scheduler, "push_schedule")
    return C


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    return mkcli(capsys, C)


# Compatible with print_yaml() function
TESTVAL = [{"a": "b"}]


def test_gen_instructor_schedule_reminder(mocker, cli):
    mocker.patch.object(
        C.builder, "get_unscheduled_instructors", return_value=[("Foo", "a@b.com")]
    )
    assert cli(
        "gen_instructor_schedule_reminder",
        ["--start", d(0).isoformat(), "--end", d(1).isoformat()],
    ) == [
        {
            "body": mocker.ANY,
            "subject": "Foo: please schedule your classes!",
            "target": "a@b.com",
        },
        {
            "body": mocker.ANY,
            "subject": "Automation notification summary",
            "target": "#class-automation",
        },
    ]


def test_gen_class_emails(cli, mocker):
    eb = mocker.patch.object(C.builder.ClassEmailBuilder, "build", return_value=TESTVAL)
    assert cli("gen_class_emails", []) == TESTVAL


Tc = namedtuple("Tc", "desc,overrides")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("Scheduled before today", {"start_time": d(-2)}),
        Tc("Too soon in future", {"start_time": d(13)}),
        Tc("Unconfirmed", {"confirmed": None}),
        Tc("Already scheduled", {"neon_id": "1234"}),
    ],
    ids=idfn,
)
def test_resolve_schedule_ignored_events(cli, mocker, tc):
    """Test cases where the scheduling action is skipped"""
    tcls = mocker.MagicMock(
        **{
            "class_id": "abcd",
            "start_time": d(20),
            "name": "test class",
            "neon_id": None,
            "confirmed": d(-1),
            "instructor_name": "inst1",
            "description": {
                "Short escrpition": "testdesc",
            },
            "image_url": "http://testimg",
            "hours": 3,
            "capacity": 6,
            "price": 90,
            "area": 90,
            "instructor_email": "a@b.com",
            **tc.overrides,
        }
    )

    mocker.patch.object(C.neon_base, "NeonOne")
    mocker.patch.object(
        C.Commands,
        "_schedule_event",
        create=True,
        side_effect=RuntimeError("Should not have scheduled"),
    )
    mocker.patch.object(
        C.airtable, "get_class_automation_schedule", return_value=[tcls]
    )
    mocker.patch.object(C, "tznow", return_value=d(0))
    assert not list(C.resolve_schedule(14, None))


def test_format_class_description(mocker):
    cmd = C.Commands()
    mocker.patch.object(
        cmd,
        "_fetch_boilerplate",
        return_value=(
            "rules_and_expectations",
            "cancellation_policy",
            "age_section_fmt",
        ),
    )

    result = cmd._format_class_description(
        mocker.MagicMock(
            image_link="link",
            description={
                "Short Description": "short_desc",
                "What you Will Create": "what_create",
                "What to Bring/Wear": "what_bring",
                "Clearances Earned": "clearances",
                "Age Requirement": "16+",
            },
            sessions=[
                (d(0, 8), d(0, 11)),
                (d(7, 8), d(7, 11)),
                (d(14, 8), d(14, 11)),
            ],
        )
    )
    assert (
        result
        == '<p><img height="200" src="link"/></p>\n<p>short_desc</p>\n<p><strong>What you Will Create</strong></p>\n<p>what_create</p>\n\n<p><strong>What to Bring/Wear</strong></p>\n<p>what_bring</p>\n\n<p><strong>Clearances Earned</strong></p>\n<p>clearances</p>\n\n<p><strong>Age Requirement</strong></p>\n<p>age_section_fmt</p><p><strong>Class Dates</strong></p>\n<ul>\n<li>Wednesday Jan 1, 8AM - 11AM</li>\n<li>Wednesday Jan 8, 8AM - 11AM</li>\n<li>Wednesday Jan 15, 8AM - 11AM</li>\n</ul><p>rules_and_expectations</p><p>cancellation_policy</p>'
    )


Tc = namedtuple("Tc", "desc,args,publish,register,discount,reserve")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("defaults", [], True, True, True, True),
        Tc("no publish", ["--no-publish"], False, True, True, True),
        Tc("no registration", ["--no-registration"], True, False, True, True),
        Tc("no discounts", ["--no-discounts"], True, True, False, True),
        Tc("no reservation", ["--no-reserve"], True, True, True, False),
    ],
    ids=idfn,
)
def test_post_classes_to_neon_actions(cli, mocker, tc):
    """Test cases where the class is scheduled, with various args applied"""
    m2 = mocker.MagicMock()
    mocker.patch.object(C.neon_base, "NeonOne", return_value=m2)
    mock_delete = mocker.patch.object(
        C.neon_base, "delete_event_unsafe", return_value=True
    )
    mocker.patch.object(C.neon_base, "create_event", return_value="123")
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
    C.neon_base.create_event.assert_called_with(
        mocker.ANY,
        mocker.ANY,
        d(30),
        d(30) + datetime.timedelta(hours=3),
        category="27",
        max_attendees=6,
        dry_run=False,
        published=tc.publish,
        registration=tc.register,
    )
    C.neon_base.create_event.mock_calls[0][0] == "Test Class"
    assert (
        '<p><img height="200" src="http://testimg"/></p>'
        in C.neon_base.create_event.mock_calls[0][1][1]
    )
    m2.assign_pricing.assert_called_with(
        "123", 90, 6, include_discounts=tc.discount, clear_existing=True
    )
    if tc.reserve:
        C.Commands._reserve_equipment_for_class_internal.assert_called_with(
            {
                "areas": {90},
                "name": ["Test Class"],
                "intervals": mocker.ANY,
                "resources": [],
            },
            True,
        )
    mock_delete.assert_not_called()


def test_post_classes_to_neon_reverts_on_failure(cli, mocker):
    """Test that class creation is reverted when part of the process fails"""
    mocker.patch.object(C.comms, "send_discord_message")
    mocker.patch.object(C.neon_base, "NeonOne")
    # Setup test data
    test_event = {
        "id": "test_id",
        "start": d(1),
        "cid": "test_cid",
        "fields": {
            "Instructor": "Test Instructor",
            "Name (from Class)": ["Test Class"],
        },
    }
    mocker.patch.object(C.Commands, "_resolve_schedule", return_value=[test_event])

    mock_delete = mocker.patch.object(
        C.neon_base, "delete_event_unsafe", return_value=True
    )
    mock_schedule = mocker.patch.object(
        C.Commands, "_schedule_event", return_value="test_event_id"
    )
    mocker.patch.object(
        C.Commands, "_format_class_description", return_value="test_description"
    )
    mock_pricing = mocker.patch.object(
        C.Commands, "_apply_pricing", side_effect=Exception("Pricing failed!")
    )
    mock_airtable = mocker.patch.object(C.airtable, "update_record")

    got = cli("post_classes_to_neon", ["--apply"])
    assert got == []

    # Verify behavior
    C.comms.send_discord_message.assert_called_with(
        MatchStr("Reverted class #test_event_id"), "#class-automation", blocking=False
    )
    mock_schedule.assert_called_once()
    mock_pricing.assert_called_once()
    mock_airtable.assert_called_once_with(
        {"Neon ID": ""}, "class_automation", "schedule", "test_id"
    )
    mock_delete.assert_called_once_with("test_event_id")
