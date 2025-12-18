"""Test for Asana task integration"""

from protohaven_api.config import safe_parse_datetime
from protohaven_api.integrations import tasks as t
from protohaven_api.testing import d


def test_get_with_onhold_section(mocker):
    """Test get_with_onhold_section for task filtering"""
    mocker.patch.object(
        t,
        "get_config",
        return_value={"test_project": {"gid": "123", "on_hold_section": "456"}},
    )
    mt = mocker.patch.object(t, "_tasks")
    mt().get_tasks_for_project.return_value = [
        {
            "completed": False,
            "memberships": [{"section": {"gid": "456"}}],
            "modified_at": d(0),
        },
        {
            "completed": False,
            "memberships": [{"section": {"gid": "789"}}],
            "modified_at": d(1),
        },
        {
            "completed": True,
            "memberships": [{"section": {"gid": "456"}}],
            "modified_at": d(2),
        },
    ]

    # Test excluding on hold tasks
    tasks = list(t.get_with_onhold_section("test_project", exclude_on_hold=True))
    assert len(tasks) == 1  # Only one task not on hold and not completed
    assert "789" in tasks[0]["sections"]

    # Test excluding completed tasks
    tasks = list(t.get_with_onhold_section("test_project", exclude_complete=True))
    assert len(tasks) == 2  # Two tasks not completed
    assert "456" in tasks[0]["sections"]
    assert "789" in tasks[1]["sections"]

    # Test excluding both on hold and completed tasks
    tasks = list(
        t.get_with_onhold_section(
            "test_project", exclude_on_hold=True, exclude_complete=True
        )
    )
    assert len(tasks) == 1  # Only one task not on hold and not completed
    assert "789" in tasks[0]["sections"]

    # Test not excluding any tasks
    tasks = list(t.get_with_onhold_section("test_project"))
    assert len(tasks) == 3  # All tasks returned
    assert "456" in tasks[0]["sections"]
    assert "789" in tasks[1]["sections"]
    assert "456" in tasks[2]["sections"]


def test_last_maintenance_completion_map(mocker):
    """Test last_maintenance_completion_map function"""
    mocker.patch.object(t, "tznow", return_value=d(0))

    tasks = [
        {
            "completed": True,
            "modified_at": "2024-12-01T00:00:00Z",
            "custom_fields": [{"name": "Origin ID", "text_value": "123"}],
        },
        {
            "completed": False,
            "modified_at": "2025-01-01T00:00:00Z",
            "custom_fields": [{"name": "Origin ID", "text_value": "456"}],
        },
    ]

    mocker.patch.object(
        t,
        "_tasks",
        return_value=mocker.Mock(get_tasks_for_project=mocker.Mock(return_value=tasks)),
    )
    mocker.patch.object(t, "get_config", return_value="some_gid")
    mocker.patch.object(
        t, "_get_maint_ref", side_effect=lambda x: x["custom_fields"][0]["text_value"]
    )

    result = t.last_maintenance_completion_map()

    expected = {"123": safe_parse_datetime("2024-12-01T00:00:00Z"), "456": d(0)}
    assert result == expected


def test_add_maintenance_task_if_not_exists(mocker):
    """Test adding a maintenance task if it does not exist"""
    mocker.patch.object(
        t,
        "get_config",
        side_effect=lambda k: {  # pylint: disable=unnecessary-lambda
            "asana/gid": "workspace_gid",
            "asana/shop_and_maintenance_tasks/custom_fields/"
            "airtable_id/gid": "airtable_custom_field_id",
            "asana/shop_and_maintenance_tasks/gid": "shop_and_maintenance_tasks_gid",
            "asana/shop_and_maintenance_tasks/tags": {
                "training_needed": "training_needed_gid",
            },
        }.get(k),
    )

    mock_tasks = mocker.patch.object(t, "_tasks")
    mock_sections = mocker.patch.object(t, "_sections")

    # Test when the task already exists
    mock_tasks().search_tasks_for_workspace.return_value = [{"gid": "existing_gid"}]
    task_gid = t.add_maintenance_task_if_not_exists(
        "Task Name", "Task Desc", "rec12345", ["training_needed"]
    )
    assert task_gid == "existing_gid"
    mock_tasks().create_task.assert_not_called()
    mock_sections().add_task_for_section.assert_not_called()

    mock_sections().get_sections_for_project.return_value = [
        {"name": "section", "gid": "section_gid"}
    ]

    # Test when the task does not exist
    mock_tasks().search_tasks_for_workspace.return_value = []
    mock_tasks().create_task.return_value = {"gid": "new_gid"}
    task_gid = t.add_maintenance_task_if_not_exists(
        "Task Name", "Task Desc", "rec12345", "training_needed", "section"
    )
    assert task_gid == "new_gid"
    mock_tasks().create_task.assert_called_once_with(
        {
            "data": {
                "projects": ["shop_and_maintenance_tasks_gid"],
                "section": "section_gid",
                "tags": ["training_needed_gid"],
                "custom_fields": {
                    "airtable_custom_field_id": "rec12345",
                },
                "name": "Task Name",
                "notes": "Task Desc",
            }
        },
        {},
    )
    mock_sections().add_task_for_section.assert_called_once_with(
        "section_gid", {"body": {"data": {"task": "new_gid"}}}
    )
