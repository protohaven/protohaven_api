"""Test for class command logic"""

from protohaven_api.commands.classes import Commands as C
from protohaven_api.integrations import neon


def test_category_from_event_name():
    """Test a few cases to make sure categories are correctly applied"""
    assert (
        C.neon_category_from_event_name("Digital 113: 2D Vector Creation")
        == neon.Category.PROJECT_BASED_WORKSHOP
    )
    assert (
        C.neon_category_from_event_name("Welding 101: MIG Welding Clearance")
        == neon.Category.SKILLS_AND_SAFETY_WORKSHOP
    )
    assert (
        C.neon_category_from_event_name("All Member Meeting")
        == neon.Category.MEMBER_EVENT
    )
    assert (
        C.neon_category_from_event_name("Valentine's Day Make & Take Party")
        == neon.Category.SOMETHING_ELSE_AMAZING
    )
