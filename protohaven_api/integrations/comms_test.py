"""Testing comms integration methods"""

import hashlib
from unittest.mock import MagicMock

import pytest

from protohaven_api.integrations import comms as c
from protohaven_api.testing import MatchStr, d


def test_send_discord_message_with_role_embed(mocker):
    """Ensure that @role mentions are properly converted to role IDs"""
    mocker.patch.object(c, "get_connector")
    c.send_discord_message("Hello @Techs!", "#techs-live")
    c.get_connector().discord_webhook.assert_called_with(  # pylint: disable=no-member
        mocker.ANY, MatchStr("Hello <@&.+?>!")
    )


def test_send_discord_message_with_user_embed(mocker):
    """Ensure that @user mentions are properly converted to user IDs"""
    mocker.patch.object(c, "get_connector")
    c.get_connector().discord_bot_fn.return_value = "userid"
    c.send_discord_message("Hello @displayname", "#techs-live")
    c.get_connector().discord_bot_fn.assert_called_with(
        "resolve_user_id", "displayname"
    )
    c.get_connector().discord_webhook.assert_called_with(  # pylint: disable=no-member
        mocker.ANY, "Hello <@userid>"
    )


def test_send_discord_message_with_user_embed_error(mocker):
    """Ensure that errors when resolving user IDs are ignored"""
    mocker.patch.object(c, "get_connector")
    c.get_connector().discord_bot_fn.side_effect = RuntimeError("test")
    c.send_discord_message("Hello @displayname", "#techs-live")
    c.get_connector().discord_webhook.assert_called_with(  # pylint: disable=no-member
        mocker.ANY, "Hello @displayname"
    )


def test_send_discord_message_dm(mocker):
    """Ensure #user targets are sent via DM"""
    mocker.patch.object(
        c,
        "get_config",
        return_value={
            "comms": {
                "test_channel": "https://test_channel_webhook",
                "discord_roles": {"TestRole": "TEST_ROLE_ID"},
            }
        },
    )
    mocker.patch.object(c, "get_connector")
    c.send_discord_message("Test content", "@testuser")
    c.get_connector().discord_bot_fn.assert_called_with(  # pylint: disable=no-member
        "send_dm", "testuser", "Test content"
    )


def test_comms_render():
    """Test that comms templates are rendered"""
    assert c.render("test_template", val="test_body") == (
        "Test Subject",
        "test_body",
        False,
    )


def test_templates_html_detection():
    """Test that templates properly detect html header"""
    _, _, got = c.render("test_template", val="test_body")
    assert not got
    _, _, got = c.render("test_html_template", val="test_body")
    assert got


TEST_EVENT = {
    "neon_id": "34567",
    "start_date": d(0),
    "name": "Test Event",
    "instructor_name": "TestInstName",
    "capacity": 6,
    "attendee_count": 3,
    "supply_cost": 0,
}
TEST_ATTENDEE = {
    "fname": "TestAttendeeName",
    "email": "test@attendee.com",
}

tech1 = MagicMock(email="a@a.com", discord_user="foobar")
tech1.name = "Tech A"
tech2 = MagicMock(email="b@b.com", discord_user=None)
tech2.name = "Tech B"

TESTED_TEMPLATES = [
    ("test_template", {"val": "test_body"}),
    ("test_html_template", {"val": "test_body"}),
    (
        "class_automation_summary",
        {
            "events": {
                "123": {
                    "action": ["FOO", "BAR"],
                    "name": "Test Action",
                    "targets": ["a", "b"],
                },
            }
        },
    ),
    ("booked_member_sync_summary", {"n": 5, "changes": [1, 2, 3]}),
    (
        "class_scheduled",
        {
            "inst": "InstName",
            "formatted": [
                {"start": "2020-01-01", "name": "Class1", "inst": "Foo"},
                {"start": "2020-01-02", "name": "Class2", "inst": "Bar"},
            ],
            "n": 2,
        },
    ),
    (
        "clearance_change_summary",
        {
            "n": 2,
            "changes": ["change 1", "change 2"],
            "errors": ["error 1", "error 2"],
        },
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
        "discord_nick_changed",
        {"prev_nick": "foo", "next_nick": "bar"},
    ),
    (
        "discord_role_change_dm",
        {
            "logs": ["Entry 1", "Entry 2"],
            "n": 2,
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
        "discount_creation_summary",
        {
            "num": 3,
            "cur_qty": "30",
            "target_qty": "50",
            "use_by": "2001-01-01",
        },
    ),
    (
        "donation_requests",
        {
            "num": 2,
            "requests": ["Req A", "Req B"],
        },
    ),
    (
        "door_sensor_warnings",
        {"warnings": ["warning1", "warning2"]},
    ),
    (
        "camera_check_warnings",
        {"warnings": ["warning1", "warning2"]},
    ),
    (
        "class_supply_requests",
        {
            "num": 1,
            "requests": [
                {
                    "days": 10,
                    "name": "Test Class",
                    "inst": "Test Instructor",
                    "date": "2000-01-01",
                }
            ],
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
        {"num": 3, "footer": "Test Footer"},
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
        {
            "classes": [
                {"start": "YYYY-MM-DD", "name": "Test Class", "inst": "Instructor"},
                {"start": "YYYY-MM-DD", "name": "Test class without instructor info"},
            ],
            "n": 3,
        },
    ),
    (
        "member_recert_update",
        {
            "fname": "Foo",
            "rm_clearance": [
                {"tool_name": "Laser 1", "last_earned": d(-20), "due_date": d(0)}
            ],
            "new_pending": [
                {"tool_name": "Table Saw 1", "last_earned": d(-10), "due_date": d(10)}
            ],
            "rm_pending": [
                {
                    "tool_name": "CNC Embroidery",
                    "last_earned": d(0),
                    "next_deadline": d(20),
                }
            ],
        },
    ),
    (
        "membership_activated",
        {"fname": "First"},
    ),
    (
        "membership_init_summary",
        {
            "summary": [
                {
                    "fname": "Fname",
                    "account_id": "123",
                    "email": "a@b.com",
                    "membership_id": "456",
                    "membership_name": "Test Membership",
                    "coupon_amount": 1000000,
                    "apply": "oh yeah",
                }
            ]
        },
    ),
    (
        "membership_validation_problems",
        {
            "problems": [
                {"name": "Test Name", "account_id": "123", "result": "Problem 1"}
            ]
        },
    ),
    ("new_project_request", {"notes": "test_notes"}),
    ("not_associated", {"discord_id": "testid"}),
    (
        "phone_message",
        {"msg_header": "stuff and things", "notes": "This is a message", "date": d(0)},
    ),
    (
        "recertification_summary",
        {"changes": ["Change 1", "Change 2"]},
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
            "onduty": [tech1, tech2],
        },
    ),
    (
        "shop_tech_applications",
        {
            "num": 3,
            "footer": "Test Footer",
        },
    ),
    (
        "square_validation_action_needed",
        {
            "unpaid": ["a", "b"],
            "untaxed": ["c", "d"],
        },
    ),
    (
        "tech_daily_tasks",
        {
            "salutation": "Whattup!",
            "new_count": 1,
            "errs": [ValueError("value or something")],
            "new_tasks": [{"name": "Test Task", "gid": "123"}],
            "closing": "Stay tested!",
            "am_tech_discord": ["@foo", "@bar"],
            "pm_tech_discord": ["@fizz", "@buzz"],
        },
    ),
    ("tech_openings", {"n": 1, "events": [TEST_EVENT]}),
    ("tool_sync_summary", {"n": 1, "changes": ["change 1", "change 2"]}),
    (
        "verify_income",
        {"fname": "First"},
    ),
    (
        "violation_ongoing",
        {
            "firstname": "Firstname",
            "start": d(0),
            "sections": ["Section A", "Section B"],
            "notes": "Detailed violation notes",
            "fee": 5,
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
    (
        "volunteer_refresh_summary",
        {
            "n": 1,
            "summary": [
                {
                    "fname": "First",
                    "lname": "Last",
                    "end_date": "2020-01-01",
                    "account_id": 12345,
                    "membership_id": 6789,
                    "new_end": "2020-02-02",
                    "membership_type": "Test Membership",
                }
            ],
        },
    ),
    (
        "wiki_backup_summary",
        {
            "stats": [
                {"name": "db.ext", "drive_id": "CDE", "size_kb": 123},
                {"name": "files.ext", "drive_id": "ABC", "size_kb": 456},
            ],
            "parent_id": "PAR",
        },
    ),
]

HASHES = {
    "test_template": "b8a27190aa3ed922",  # pragma: allowlist secret
    "test_html_template": "77606b5538c73e78",  # pragma: allowlist secret
    "booked_member_sync_summary": "cc0dd6700111fd41",  # pragma: allowlist secret
    "class_automation_summary": "866427c2de1c186f",  # pragma: allowlist secret
    "class_scheduled": "b57307cca2f8262c",  # pragma: allowlist secret
    "clearance_change_summary": "98410280f08a0823",  # pragma: allowlist secret
    "daily_private_instruction": "ba81765c045917ee",  # pragma: allowlist secret
    "discord_nick_change_summary": "88493fe928a1f0d4",  # pragma: allowlist secret
    "discord_nick_changed": "8aeda50de8ef931c",  # pragma: allowlist secret
    "discord_role_change_dm": "e36c6c70681a8804",  # pragma: allowlist secret
    "discord_role_change_summary": "8a34d924f30d0625",  # pragma: allowlist secret
    "discount_creation_summary": "e3c5a08c4933b6b3",  # pragma: allowlist secret
    "donation_requests": "a7c0cc5126341eb4",  # pragma: allowlist secret
    "door_sensor_warnings": "4203149c4b940078",  # pragma: allowlist secret
    "camera_check_warnings": "76c49eadc52a688d",  # pragma: allowlist secret
    "class_supply_requests": "3e12f3737ad31808",  # pragma: allowlist secret
    "enforcement_summary": "18d1792e7afc0c24",  # pragma: allowlist secret
    "init_membership": "c7d1c2cd9a12411e",  # pragma: allowlist secret
    "instruction_requests": "64096a3f590a8f43",  # pragma: allowlist secret
    "instructor_applications": "500fced2472831c6",  # pragma: allowlist secret
    "instructor_check_supplies": "73815da04e9f47cc",  # pragma: allowlist secret
    "instructor_class_canceled": "57dc5ce8d4ec5317",  # pragma: allowlist secret
    "instructor_class_confirmed": "51392e2fb41f37f8",  # pragma: allowlist secret
    "instructor_log_reminder": "d00bf87676ad240e",  # pragma: allowlist secret
    "instructor_low_attendance": "e7b4548a7a3f7fc2",  # pragma: allowlist secret
    "instructor_schedule_classes": "39aea10c71fc8895",  # pragma: allowlist secret
    "instructors_new_classes": "43f58a36632acefb",  # pragma: allowlist secret
    "member_recert_update": "ca7964a8b68ee4be",  # pragma: allowlist secret
    "membership_activated": "8a27b2ff8900b48b",  # pragma: allowlist secret
    "membership_init_summary": "c4503d766704f3ec",  # pragma: allowlist secret
    "membership_validation_problems": "07e7e586afd0dd5e",  # pragma: allowlist secret
    "new_project_request": "4cffeae1816d93a2",  # pragma: allowlist secret
    "not_associated": "4368092931234979",  # pragma: allowlist secret
    "phone_message": "c17d7359c5ddace4",  # pragma: allowlist secret
    "recertification_summary": "a360e54dcfdbe688",  # pragma: allowlist secret
    "registrant_class_canceled": "a3b36f01fde3ee4c",  # pragma: allowlist secret
    "registrant_class_confirmed": "d6c0ac936f4c44dd",  # pragma: allowlist secret
    "registrant_post_class_survey": "7f89d4a2a4211f67",  # pragma: allowlist secret
    "schedule_push_notification": "fdb8409ccac4ba4b",  # pragma: allowlist secret
    "shift_no_techs": "28da9194d12b5db6",  # pragma: allowlist secret
    "shop_tech_applications": "a011ed984ed4a302",  # pragma: allowlist secret
    "square_validation_action_needed": "8cf97c894e5171aa",  # pragma: allowlist secret
    "tech_daily_tasks": "950fc9858cdf56bd",  # pragma: allowlist secret
    "tech_openings": "dad9368b3192d473",  # pragma: allowlist secret
    "tool_sync_summary": "dcc01eae3a3b66a3",  # pragma: allowlist secret
    "verify_income": "4d24d1a819192eae",  # pragma: allowlist secret
    "violation_ongoing": "fcad4dda2bb81f53",  # pragma: allowlist secret
    "violation_started": "12527581a8fbdd2d",  # pragma: allowlist secret
    "volunteer_refresh_summary": "a2858fc78352ea01",  # pragma: allowlist secret
    "wiki_backup_summary": "453ee303bc5f3a02",  # pragma: allowlist secret
}


def _gethash(data):
    h = hashlib.sha256()
    h.update(bytes(f"{data}", encoding="utf8"))
    return h.hexdigest()[:16]


@pytest.mark.parametrize("template_name, template_kwargs", TESTED_TEMPLATES)
def test_template_rendering(template_name, template_kwargs):
    """Test jinja templates with dummy arguments, ensuring they match
    the prior hash
    """
    got = c.render(template_name, **template_kwargs)
    gothash = _gethash(got)
    wanthash = HASHES[template_name]
    if gothash != wanthash:
        raise RuntimeError(
            f"Test output hash {gothash} does not match prior hash {wanthash}:\n"
            f"Template: {template_name}\n"
            f"Subject: '{got[0]}'\n"
            f"Body: '{got[1]}'\n"
            f"HTML: {got[2]}\n"
            f"Update HASHES['{template_name}'] = '{gothash}'"
        )
    assert got[0] != got[1]  # Subject should never match body


@pytest.mark.parametrize("tmpl", c.get_all_templates())
def test_all_templates_tested(tmpl):
    """Ensure that we have at least one test for every template file"""
    tested_templates = {t[0] for t in TESTED_TEMPLATES}
    assert tmpl in tested_templates


if __name__ == "__main__":
    hashes = {}
    for i, ttt in enumerate(TESTED_TEMPLATES):
        tname, kwargs = ttt
        hashes[tname] = _gethash(c.render(tname, **kwargs))  # type: ignore[arg-type]
    print(hashes)
