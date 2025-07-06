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
