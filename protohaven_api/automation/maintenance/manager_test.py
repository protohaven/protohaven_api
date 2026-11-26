"""Tests for maintenance manager module"""

from protohaven_api.automation.maintenance import manager as m
from protohaven_api.testing import d


def test_get_maintenance_needed_tasks(mocker):
    """Test get_maintenance_needed_tasks for wiki-sourced tasks."""
    # Mock the dependencies
    mocker.patch.object(m, "tznow", return_value=d(0))
    mocker.patch.object(
        m.tasks, "last_maintenance_completion_map", return_value={"task_1": d(0)}
    )
    mocker.patch.object(m, "get_config", return_value=["book-slug"])
    mocker.patch.object(
        m.wiki,
        "get_maintenance_data",
        return_value=[
            {
                "maint_ref": "task_1",
                "maint_task": "Check Inventory",
                "book_slug": "maintenance",
                "page_slug": "inventory-check",
                "approval_state": {"approved_revision": True, "approved_id": "rev_1"},
                "maint_freq_days": 7,
                "maint_level": "admin_required",
                "maint_asana_section": "Shop Section",
            }
        ],
    )
    # Too soon
    needed_tasks = m.get_maintenance_needed_tasks(d(2))
    assert len(needed_tasks) == 0

    # After freq timeout
    needed_tasks = m.get_maintenance_needed_tasks(d(8))
    assert len(needed_tasks) == 1
    assert needed_tasks[0]["id"] == "task_1"
    assert needed_tasks[0]["origin"] == "Bookstack"
    assert needed_tasks[0]["name"] == "Check Inventory"
    assert needed_tasks[0]["section"] == "Shop Section"
    assert needed_tasks[0]["level"] == "admin_required"


def test_unapproved_wiki_tasks_not_returned(mocker):
    """Ensure unapproved wiki tasks aren't returned on calls to
    get_maintenance_needed_tasks"""
    mocker.patch.object(m, "tznow", return_value=d(0))
    mocker.patch.object(m.tasks, "_resolve_section_gid", return_value=None)
    mocker.patch.object(m.tasks, "last_maintenance_completion_map", return_value={})
    mocker.patch.object(m, "get_config", return_value=["book-slug"])
    mocker.patch.object(
        m.wiki,
        "get_maintenance_data",
        return_value=[
            {
                "maint_ref": "task1",
                "maint_task": "Unapproved Task",
                "book_slug": "book1",
                "page_slug": "page1",
                "maint_level": "training_required",
                "approval_state": {},
                "maint_freq_days": 10,
            },
            {
                "maint_ref": "task2",
                "maint_task": "Approved Task",
                "book_slug": "book2",
                "page_slug": "page2",
                "maint_level": "admin_required",
                "approval_state": {"approved_revision": "rev1", "approved_id": "123"},
                "maint_freq_days": 5,
            },
        ],
    )

    got = m.get_maintenance_needed_tasks(d(0))
    assert len(got) == 1
    assert got[0]["id"] == "task2"


def test_missing_tag_skips_task_and_notifies_tech_automation(mocker):
    """Malformed Bookstack tasks are skipped and reported to #tech-automation
    rather than failing the entire maintenance generation run."""
    mocker.patch.object(m, "tznow", return_value=d(0))
    mocker.patch.object(m.tasks, "last_maintenance_completion_map", return_value={})
    mocker.patch.object(m, "get_config", return_value=["book-slug"])
    mocker.patch.object(
        m.wiki,
        "get_maintenance_data",
        return_value=[
            {
                "maint_ref": "bad-task",
                "maint_task": "Missing Level Tag",
                "book_slug": "maintenance",
                "page_slug": "missing-level",
                "approval_state": {"approved_revision": "rev1"},
                "maint_freq_days": 7,
            },
            {
                "maint_ref": "good-task",
                "maint_task": "Valid Task",
                "book_slug": "maintenance",
                "page_slug": "valid-task",
                "approval_state": {"approved_revision": "rev1"},
                "maint_freq_days": 7,
                "maint_level": "tech_ready",
            },
        ],
    )
    send = mocker.patch.object(m.comms, "send_discord_message")

    got = m.get_maintenance_needed_tasks(d(0))

    assert len(got) == 1
    assert got[0]["id"] == "good-task"
    send.assert_called_once()
    assert send.call_args.args[1] == "#tech-automation"
    assert "maint_level" in send.call_args.args[0]


def test_invalid_freq_skips_task_and_notifies_tech_automation(mocker):
    """Tasks with a non-integer maint_freq_days are skipped and reported."""
    mocker.patch.object(m, "tznow", return_value=d(0))
    mocker.patch.object(m.tasks, "last_maintenance_completion_map", return_value={})
    mocker.patch.object(m, "get_config", return_value=["book-slug"])
    mocker.patch.object(
        m.wiki,
        "get_maintenance_data",
        return_value=[
            {
                "maint_ref": "bad-task",
                "maint_task": "Bad Frequency",
                "book_slug": "maintenance",
                "page_slug": "bad-frequency",
                "approval_state": {"approved_revision": "rev1"},
                "maint_freq_days": "weekly",
                "maint_level": "tech_ready",
            }
        ],
    )
    send = mocker.patch.object(m.comms, "send_discord_message")

    got = m.get_maintenance_needed_tasks(d(0))

    assert not got
    send.assert_called_once()
    assert send.call_args.args[1] == "#tech-automation"
    assert "maint_freq_days" in send.call_args.args[0]


def test_get_recent_tool_status_changes(mocker):
    """Tool status changes are limited to the last 24h and red/yellow/green states."""
    mocker.patch.object(
        m.airtable,
        "get_tools",
        return_value=[
            {
                "id": "rec1",
                "fields": {
                    "Tool Name": "SawStop",
                    "Tool Code": "SAW",
                    "Current Status": "Red (needs repair)",
                    "Status last modified": d(0, h=11).isoformat(),
                },
            },
            {
                "id": "rec2",
                "fields": {
                    "Tool Name": "Laser Cutter",
                    "Tool Code": "LAS",
                    "Current Status": "Yellow",
                    "Status last modified": d(0, h=10).isoformat(),
                },
            },
            {
                "id": "rec3",
                "fields": {
                    "Tool Name": "Planer",
                    "Tool Code": "PLN",
                    "Current Status": "Green (fully operational)",
                    "Status last modified": d(-2).isoformat(),
                },
            },
            {
                "id": "rec4",
                "fields": {
                    "Tool Name": "Drill Press",
                    "Tool Code": "DRL",
                    "Current Status": "Blue",
                    "Status last modified": d(0, h=10).isoformat(),
                },
            },
            {
                "id": "rec5",
                "fields": {
                    "Tool Name": "Band Saw",
                    "Tool Code": "BND",
                    "Current Status": "Green",
                },
            },
            {
                "id": "rec1",
                "fields": {
                    "Tool Name": "SawStop",
                    "Tool Code": "SAW",
                    "Current Status": "Red (needs repair)",
                    "Status last modified": d(0, h=11).isoformat(),
                },
            },
        ],
    )

    def reports(tool_id, back_days=90):
        assert back_days == 90
        if tool_id == "rec1":
            return [
                {"t": d(0, h=9), "state": "Green (fully operational)"},
                {"t": d(0, h=11), "state": "Red (needs repair)"},
            ]
        if tool_id == "rec2":
            return [
                {"t": d(0, h=8), "state": "Red"},
                {"t": d(0, h=10), "state": "Yellow"},
            ]
        return []

    report_fn = mocker.patch.object(
        m.airtable, "get_reports_for_tool", side_effect=reports
    )

    got = m.get_recent_tool_status_changes(now=d(0, h=12), hours=24)

    assert report_fn.call_count == 2  # rec1 is deduplicated
    assert got["counts"] == {"red": 1, "yellow": 1, "green": 0}
    assert got["changed"] == [
        {"name": "SawStop (SAW)", "status": "red", "previous": "green"},
        {"name": "Laser Cutter (LAS)", "status": "yellow", "previous": "red"},
    ]


def test_get_recent_tool_status_changes_skips_unchanged(mocker):
    """A tool is skipped when its latest report history shows no color change."""
    mocker.patch.object(
        m.airtable,
        "get_tools",
        return_value=[
            {
                "id": "rec1",
                "fields": {
                    "Tool Name": "SawStop",
                    "Current Status": "Red",
                    "Status last modified": d(0, h=11).isoformat(),
                },
            }
        ],
    )
    mocker.patch.object(
        m.airtable,
        "get_reports_for_tool",
        return_value=[{"t": d(0, h=10), "state": "Red"}],
    )

    got = m.get_recent_tool_status_changes(now=d(0, h=12), hours=24)

    assert got == {"changed": [], "counts": {"red": 0, "yellow": 0, "green": 0}}


def test_get_recent_tool_status_changes_unknown_previous(mocker):
    """A tool with no prior report history is shown with an unknown previous status."""
    mocker.patch.object(
        m.airtable,
        "get_tools",
        return_value=[
            {
                "id": "rec1",
                "fields": {
                    "Tool Name": "SawStop",
                    "Current Status": "Red",
                    "Status last modified": d(0, h=11).isoformat(),
                },
            }
        ],
    )
    mocker.patch.object(m.airtable, "get_reports_for_tool", return_value=[])

    got = m.get_recent_tool_status_changes(now=d(0, h=12), hours=24)

    assert got == {
        "changed": [{"name": "SawStop", "status": "red", "previous": "unknown"}],
        "counts": {"red": 1, "yellow": 0, "green": 0},
    }


def test_get_recent_tool_status_changes_bad_timestamp_skipped(mocker):
    """Tools with unparseable status timestamps are skipped, not fatal."""
    mocker.patch.object(
        m.airtable,
        "get_tools",
        return_value=[
            {
                "id": "rec1",
                "fields": {
                    "Tool Name": "SawStop",
                    "Current Status": "Red",
                    "Status last modified": "not-a-date",
                },
            }
        ],
    )

    got = m.get_recent_tool_status_changes(now=d(0, h=12), hours=24)

    assert got == {"changed": [], "counts": {"red": 0, "yellow": 0, "green": 0}}
