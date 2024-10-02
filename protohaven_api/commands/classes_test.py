"""Test for class command logic"""
# pylint: skip-file

from protohaven_api.commands import classes as C
from protohaven_api.integrations import neon


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


def test_post_classes_to_neon_zero(mocker, capsys):
    """Confirm that when there are no classes to schedule, we send no notifications"""
    mocker.patch.object(
        C.airtable,
        "get_all_records",
        return_value=[
            {"fields": ff}
            for ff in [
                {"Notes": "", "Name": "Rules & Expectations"},
                {"Notes": "", "Name": "Cancellation Policy"},
                {"Notes": "", "Name": "Age Requirement"},
            ]
        ],
    )
    mocker.patch.object(C.airtable, "get_class_automation_schedule", return_value=[])
    mocker.patch.object(C, "neon")
    C.Commands.post_classes_to_neon("/asdf/ghjk", ["--apply"])
    captured = capsys.readouterr()
    assert captured.out.strip() == "[]"
