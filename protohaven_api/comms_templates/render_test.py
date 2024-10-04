"""Unit tests for comms_templates module"""
import os
from pathlib import Path

import pytest

from protohaven_api.comms_templates import get_all_templates, render
from protohaven_api.testing import d

WANTFILE_DIR = Path(__file__).parent / "testdata/"


def test_comms_render():
    """Test that comms templates are rendered"""
    assert render("test_template", val="test_body") == (
        "Test Subject",
        "test_body",
        False,
    )


def test_templates_html_detection():
    """Test that templates properly detect html header"""
    _, _, got = render("test_template")
    assert not got
    _, _, got = render("test_html_template")
    assert got


def load_wantfile(name):
    """Loads a file representing expected outcome of running the test"""
    with open(os.path.join(WANTFILE_DIR, f"{name}.txt"), "r", encoding="utf8") as file:
        data = file.read().strip()
    lines = data.splitlines()
    assert len(lines) >= 3
    return lines[1].strip(), "\n".join(lines[2:]).strip(), lines[0] == "True"


TEST_EVENT = {
    "python_date": d(0),
    "name": "Test Event",
    "instructor_firstname": "TestInstName",
    "capacity": 6,
    "signups": 3,
}
TEST_ATTENDEE = {
    "firstName": "TestAttendeeName",
}
TESTED_TEMPLATES = [
    ("test_template", {"val": "test_body"}, "test_template"),
    ("test_html_template", {"val": "test_body"}, "test_html_template"),
    ("admin_create_suspension", {}, "admin_create_suspension"),
    (
        "class_automation_summary",
        {
            "events": {
                "123": {
                    "actions": ["FOO", "BAR"],
                    "name": "Test Action",
                    "targets": ["a", "b"],
                },
            }
        },
        "class_automation_summary",
    ),
    ("class_proposals", {}, "class_proposals"),
    ("class_scheduled", {}, "class_scheduled"),
    ("daily_private_instruction", {}, "daily_private_instruction"),
    ("discord_nick_change_summary", {"n": 2, "m": 1}, "discord_nick_change_summary"),
    ("discord_role_change_dm", {}, "discord_role_change_dm"),
    ("discord_role_change_summary", {}, "discord_role_change_summary"),
    ("enforcement_summary", {}, "enforcement_summary"),
    ("init_membership", {}, "init_membership"),
    ("instruction_requests", {}, "instruction_requests"),
    ("instructor_applications", {}, "instructor_applications"),
    ("instructor_check_supplies", {"evt": TEST_EVENT}, "instructor_check_supplies"),
    ("instructor_class_canceled", {"evt": TEST_EVENT}, "instructor_class_canceled"),
    ("instructor_class_confirmed", {"evt": TEST_EVENT}, "instructor_class_confirmed"),
    ("instructor_log_reminder", {"evt": TEST_EVENT}, "instructor_log_reminder"),
    ("instructor_low_attendance", {"evt": TEST_EVENT}, "instructor_low_attendance"),
    ("instructor_schedule_classes", {}, "instructor_schedule_classes"),
    (
        "instructors_new_classes",
        {"formatted": ["a", "b", "c"]},
        "instructors_new_classes",
    ),
    ("membership_validation_problems", {}, "membership_validation_problems"),
    ("new_project_request", {"notes": "test_notes"}, "new_project_request"),
    ("not_associated", {}, "not_associated"),
    ("phone_message", {}, "phone_message"),
    (
        "registrant_class_canceled",
        {"evt": TEST_EVENT, "a": TEST_ATTENDEE},
        "registrant_class_canceled",
    ),
    (
        "registrant_class_confirmed",
        {"evt": TEST_EVENT, "a": TEST_ATTENDEE, "now": d(-1)},
        "registrant_class_confirmed",
    ),
    (
        "registrant_post_class_survey",
        {"evt": TEST_EVENT, "a": TEST_ATTENDEE},
        "registrant_post_class_survey",
    ),
    ("schedule_push_notification", {}, "schedule_push_notification"),
    ("shift_no_techs", {}, "shift_no_techs"),
    ("shop_tech_applications", {}, "shop_tech_applications"),
    (
        "square_validation_action_needed",
        {
            "unpaid": ["a", "b"],
            "untaxed": ["c", "d"],
        },
        "square_validation_action_needed",
    ),
    ("suspension_ended", {}, "suspension_ended"),
    ("suspension_started", {"accrued": 100}, "suspension_started"),
    ("tech_daily_tasks", {"new_count": 3}, "tech_daily_tasks"),
    ("tech_leads_maintenance_status", {}, "tech_leads_maintenance_status"),
    ("tech_openings", {"events": [TEST_EVENT]}, "tech_openings"),
    ("tool_documentation", {}, "tool_documentation"),
    ("violation_ongoing", {"accrued": 10}, "violation_ongoing"),
    ("violation_started", {"fee": 5}, "violation_started"),
]


@pytest.mark.parametrize("template_name, kwargs, wantfile", TESTED_TEMPLATES)
def test_template_rendering(template_name, kwargs, wantfile):
    """Test jinja templates with dummy arguments, ensuring they match
    the wantfiles"""
    got = render(template_name, **kwargs)
    want = load_wantfile(wantfile)
    if got != want:
        raise RuntimeError(
            f"Mismatch between render of template {template_name}(**{kwargs}) and "
            f"test file {wantfile}:\n\n==== WANTED ===\n{want}\n==== GOT ===\n{got}\n\n"
            "To regenerate all test files, run python3 -m "
            "protohaven_api.comms_templates.render_test"
        )
    assert got[0] != got[1]  # Subject should never match body


@pytest.mark.parametrize("tmpl", get_all_templates())
def test_all_templates_tested(tmpl):
    """Ensure that we have at least one test for every template file"""
    tested_templates = {t[0] for t in TESTED_TEMPLATES}
    assert tmpl in tested_templates


def rerender_wantfiles():
    """Render templates with the test kwargs into files in testdata/"""
    for template_name, kwargs, wantfile in TESTED_TEMPLATES:
        with open(
            os.path.join(WANTFILE_DIR, f"{wantfile}.txt"), "w", encoding="utf8"
        ) as file:
            subject, body, is_html = render(template_name, **kwargs)
            file.write(f"{is_html}\n{subject}\n{body}")
            print(f"Wrote {wantfile}.txt")
    print("Done")


if __name__ == "__main__":
    input(
        "Press Enter to render all templates into testdata/. This will overwrite file data!"
    )
    rerender_wantfiles()
