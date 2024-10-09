"""Unit tests for comms_templates module"""
import hashlib

import pytest

from protohaven_api.comms_templates import get_all_templates, render
from protohaven_api.testing import d


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


TEST_EVENT = {
    "id": "34567",
    "python_date": d(0),
    "name": "Test Event",
    "instructor_firstname": "TestInstName",
    "capacity": 6,
    "signups": 3,
}
TEST_ATTENDEE = {
    "firstName": "TestAttendeeName",
    "email": "test@attendee.com",
}
TESTED_TEMPLATES = [
    ("test_template", {"val": "test_body"}),
    ("test_html_template", {"val": "test_body"}),
    (
        "admin_create_suspension",
        {"neon_id": 12345, "end": d(0)},
    ),
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
    ),
    ("class_proposals", {"unapproved": ["Unap1", "Unap2"]}),
    (
        "class_scheduled",
        {"inst": "InstName", "formatted": ["Class1", "Class2"], "n": 2},
    ),
    (
        "daily_private_instruction",
        {"formatted": ["Req 1", "Req 2"]},
    ),
    (
        "discord_nick_change_summary",
        {"n": 2, "changes": ["Name1", "Name2"], "m": 1, "notified": ["testuser"]},
    ),
    (
        "discord_role_change_dm",
        {
            "logs": ["Entry 1", "Entry 2"],
            "not_associated": True,
            "discord_id": "testid",
        },
    ),
    (
        "discord_role_change_summary",
        {
            "n": 2,
            "users": ["UserA", "UserB"],
            "roles_assigned": 3,
            "roles_revoked": 3,
            "footer": "Test Footer",
        },
    ),
    (
        "enforcement_summary",
        {
            "vs": [{"onset": d(0), "fee": 5, "unpaid": 10, "notes": "Test violation"}],
            "ss": [{"start": d(0), "end": d(1)}],
        },
    ),
    (
        "init_membership",
        {
            "fname": "Fname",
            "coupon_code": "ASDF",
            "coupon_amount": 5,
            "sample_classes": [
                {"date": d(0), "name": "class1", "remaining": 3, "id": 1},
                {"date": d(1), "name": "class2", "remaining": 2, "id": 2},
            ],
        },
    ),
    (
        "instruction_requests",
        {"num": 3, "formatted": ["req 1", "req 2", "req 3"]},
    ),
    (
        "instructor_applications",
        {"open_applicants": ["Foo", "Bar", "Baz"]},
    ),
    ("instructor_check_supplies", {"evt": TEST_EVENT}),
    ("instructor_class_canceled", {"evt": TEST_EVENT}),
    ("instructor_class_confirmed", {"evt": TEST_EVENT}),
    ("instructor_log_reminder", {"evt": TEST_EVENT}),
    ("instructor_low_attendance", {"evt": TEST_EVENT}),
    (
        "instructor_schedule_classes",
        {"firstname": "Firstname", "start": d(0), "end": d(30)},
    ),
    (
        "instructors_new_classes",
        {"formatted": ["a", "b", "c"], "n": 3},
    ),
    (
        "membership_activated",
        {"fname": "First"},
    ),
    (
        "membership_validation_problems",
        {"problems": ["Problem 1", "Problem 2"]},
    ),
    ("new_project_request", {"notes": "test_notes"}),
    ("not_associated", {"discord_id": "testid"}),
    (
        "phone_message",
        {"msg_header": "stuff and things", "notes": "This is a message", "date": d(0)},
    ),
    (
        "registrant_class_canceled",
        {"evt": TEST_EVENT, "a": TEST_ATTENDEE},
    ),
    (
        "registrant_class_confirmed",
        {"evt": TEST_EVENT, "a": TEST_ATTENDEE, "now": d(-1)},
    ),
    (
        "registrant_post_class_survey",
        {"evt": TEST_EVENT, "a": TEST_ATTENDEE},
    ),
    (
        "schedule_push_notification",
        {"title": "TestTitle", "formatted": ["a", "b", "c"]},
    ),
    (
        "shift_no_techs",
        {
            "shift": "Monwednesaturday TM",
            "onduty": [("Tech A", "a@a.com"), ("Tech B", "b@b.com")],
        },
    ),
    (
        "shop_tech_applications",
        {"open_applicants": ["Foo", "Bar", "Baz"]},
    ),
    (
        "square_validation_action_needed",
        {
            "unpaid": ["a", "b"],
            "untaxed": ["c", "d"],
        },
    ),
    (
        "stale_purchase_requests",
        {
            "sections": [
                {
                    "name": "section1",
                    "counts": 2,
                    "threshold": 5,
                    "tasks": ["t1", "t2"],
                },
                {
                    "name": "section2",
                    "counts": 2,
                    "threshold": 5,
                    "tasks": ["t3", "t4"],
                },
            ]
        },
    ),
    ("suspension_ended", {"firstname": "Firstname"}),
    (
        "suspension_started",
        {
            "firstname": "Firstname",
            "suffix": " for testing purposes",
            "start": d(0),
            "accrued": 100,
        },
    ),
    (
        "tech_daily_tasks",
        {
            "salutation": "Whattup!",
            "new_count": 1,
            "new_tasks": [{"name": "Test Task", "gid": "123"}],
            "closing": "Stay tested!",
        },
    ),
    (
        "tech_leads_maintenance_status",
        {
            "stale_count": 1,
            "stale_thresh": 999,
            "stale_tasks": [{"name": "Test Task", "gid": "123", "days_ago": 9001}],
        },
    ),
    ("tech_openings", {"n": 1, "events": [TEST_EVENT]}),
    (
        "tool_documentation",
        {"n": 1, "tool_tutorials": "tutorial info", "clearance_docs": "clearance info"},
    ),
    (
        "violation_ongoing",
        {
            "firstname": "Firstname",
            "start": d(0),
            "sections": ["Section A", "Section B"],
            "notes": "Detailed violation notes",
            "accrued": 10,
        },
    ),
    (
        "violation_started",
        {
            "firstname": "Firstname",
            "start": d(0),
            "notes": "Detailed violation notes",
            "sections": ["Section A", "Section B"],
            "fee": 5,
        },
    ),
]
HASHES = {
    "test_template": "b8a27190aa3ed922",
    "test_html_template": "77606b5538c73e78",
    "admin_create_suspension": "b43c46a0f86ee0d7",
    "class_automation_summary": "866427c2de1c186f",
    "class_proposals": "1d1bef17435d88da",
    "class_scheduled": "d7638c67655ae1eb",
    "daily_private_instruction": "ba81765c045917ee",
    "discord_nick_change_summary": "88493fe928a1f0d4",
    "discord_role_change_dm": "e36c6c70681a8804",
    "discord_role_change_summary": "8a34d924f30d0625",
    "enforcement_summary": "53728e884f150eec",
    "init_membership": "44cc465d9fe6e95d",
    "instruction_requests": "7e0902003add426d",
    "instructor_applications": "282f1d709883f273",
    "instructor_check_supplies": "73815da04e9f47cc",
    "instructor_class_canceled": "57dc5ce8d4ec5317",
    "instructor_class_confirmed": "51392e2fb41f37f8",
    "instructor_log_reminder": "d00bf87676ad240e",
    "instructor_low_attendance": "e7b4548a7a3f7fc2",
    "instructor_schedule_classes": "39aea10c71fc8895",
    "instructors_new_classes": "c3cbf1129a256abe",
    "membership_activated": "8a27b2ff8900b48b",
    "membership_validation_problems": "959c9f70f5ab648e",
    "new_project_request": "4cffeae1816d93a2",
    "not_associated": "4368092931234979",
    "phone_message": "c17d7359c5ddace4",
    "registrant_class_canceled": "a3b36f01fde3ee4c",
    "registrant_class_confirmed": "38e0456bdb64d363",
    "registrant_post_class_survey": "7f89d4a2a4211f67",
    "schedule_push_notification": "78908794e790a632",
    "shift_no_techs": "9a2c858ff7ac2456",
    "shop_tech_applications": "cd77b6978d522da3",
    "square_validation_action_needed": "3ed4e73c9efa37db",
    "stale_purchase_requests": "a335498511580ac9",
    "suspension_ended": "d05255f2fcb8e992",
    "suspension_started": "3b211a9a7c04be8a",
    "tech_daily_tasks": "55af86e04ce2551c",
    "tech_leads_maintenance_status": "e763f572fa0203a5",
    "tech_openings": "f9bd7999e37d1ebd",
    "tool_documentation": "30faa1dfb4e04a20",
    "violation_ongoing": "1ff24f039d2d424a",
    "violation_started": "12527581a8fbdd2d",
}


def _gethash(data):
    h = hashlib.sha256()
    h.update(bytes(f"{data}", encoding="utf8"))
    return h.hexdigest()[:16]


@pytest.mark.parametrize("template_name, kwargs", TESTED_TEMPLATES)
def test_template_rendering(template_name, kwargs):
    """Test jinja templates with dummy arguments, ensuring they match
    the prior hash"""
    got = render(template_name, **kwargs)
    gothash = _gethash(got)
    wanthash = HASHES[template_name]
    if gothash != wanthash:
        raise RuntimeError(
            f"Test output hash {gothash} does not match prior hash {wanthash}:\n"
            f"{got[0]}\n{got[1]}\n{got[2]}"
        )
    assert got[0] != got[1]  # Subject should never match body


@pytest.mark.parametrize("tmpl", get_all_templates())
def test_all_templates_tested(tmpl):
    """Ensure that we have at least one test for every template file"""
    tested_templates = {t[0] for t in TESTED_TEMPLATES}
    assert tmpl in tested_templates


if __name__ == "__main__":
    hashes = {}
    for i, ttt in enumerate(TESTED_TEMPLATES):
        hashes[ttt[0]] = _gethash(render(*ttt))
    print(hashes)
