"""Test for Asana task integration"""

from dateutil import parser as dateparser

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
        {"completed": False, "memberships": [{"section": {"gid": "456"}}]},
        {"completed": False, "memberships": [{"section": {"gid": "789"}}]},
        {"completed": True, "memberships": [{"section": {"gid": "456"}}]},
    ]

    # Test excluding on hold tasks
    tasks = list(t.get_with_onhold_section("test_project", exclude_on_hold=True))
    assert len(tasks) == 1  # Only one task not on hold and not completed
    assert tasks[0]["memberships"][0]["section"]["gid"] == "789"

    # Test excluding completed tasks
    tasks = list(t.get_with_onhold_section("test_project", exclude_complete=True))
    assert len(tasks) == 2  # Two tasks not completed
    assert tasks[0]["memberships"][0]["section"]["gid"] == "456"
    assert tasks[1]["memberships"][0]["section"]["gid"] == "789"

    # Test excluding both on hold and completed tasks
    tasks = list(
        t.get_with_onhold_section(
            "test_project", exclude_on_hold=True, exclude_complete=True
        )
    )
    assert len(tasks) == 1  # Only one task not on hold and not completed
    assert tasks[0]["memberships"][0]["section"]["gid"] == "789"

    # Test not excluding any tasks
    tasks = list(t.get_with_onhold_section("test_project"))
    assert len(tasks) == 3  # All tasks returned
    assert tasks[0]["memberships"][0]["section"]["gid"] == "456"
    assert tasks[1]["memberships"][0]["section"]["gid"] == "789"
    assert tasks[2]["memberships"][0]["section"]["gid"] == "456"


def test_get_open_purchase_requests(mocker):
    """Test get_open_purchase_requests function"""
    mt = mocker.patch.object(t, "_tasks")
    mt().get_tasks_for_project.return_value = [
        {
            "completed": False,
            "memberships": [{"section": {"gid": "requested"}}],
            "created_at": "2023-10-01T00:00:00Z",
            "modified_at": "2023-10-02T00:00:00Z",
        },
        {
            "completed": True,
            "memberships": [{"section": {"gid": "approved"}}],
            "created_at": "2023-10-03T00:00:00Z",
            "modified_at": "2023-10-04T00:00:00Z",
        },
    ]
    mocker.patch.object(
        t,
        "get_config",
        side_effect=lambda x: {
            "asana/purchase_requests/gid": "some_gid",
            "asana/purchase_requests/sections": {
                "requested": "requested",
                "approved": "approved",
                "ordered": "ordered",
                "on_hold": "on_hold",
            },
        }[x],
    )

    result = list(t.get_open_purchase_requests())
    assert len(result) == 1
    assert result[0]["category"] == "requested"
    assert result[0]["created_at"] == dateparser.parse("2023-10-01T00:00:00Z")
    assert result[0]["modified_at"] == dateparser.parse("2023-10-02T00:00:00Z")


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
        t, "get_airtable_id", side_effect=lambda x: x["custom_fields"][0]["text_value"]
    )

    result = t.last_maintenance_completion_map()

    expected = {"123": dateparser.parse("2024-12-01T00:00:00Z"), "456": d(0)}
    assert result == expected


def test_add_maintenance_task_if_not_exists(mocker):
    """Test adding a maintenance task if it does not exist"""
    mocker.patch.object(
        t,
        "get_config",
        side_effect=lambda k: {  # pylint: disable=unnecessary-lambda
            "asana/gid": "workspace_gid",
            "asana/custom_field_airtable_id": "airtable_custom_field_id",
            "asana/techs_project/gid": "techs_project_gid",
            "asana/tech_ready_tag": "tech_ready_tag",
        }.get(k),
    )

    mock_tasks = mocker.patch.object(t, "_tasks")
    mock_sections = mocker.patch.object(t, "_sections")

    # Test when the task already exists
    mock_tasks().search_tasks_for_workspace.return_value = [{"gid": "existing_gid"}]
    task_gid = t.add_maintenance_task_if_not_exists("Task Name", "Task Desc", "12345")
    assert task_gid == "existing_gid"
    mock_tasks().create_task.assert_not_called()
    mock_sections().add_task_for_section.assert_not_called()

    # Test when the task does not exist
    mock_tasks().search_tasks_for_workspace.return_value = []
    mock_tasks().create_task.return_value = {"gid": "new_gid"}
    task_gid = t.add_maintenance_task_if_not_exists(
        "Task Name", "Task Desc", "12345", "section_gid"
    )
    assert task_gid == "new_gid"
    mock_tasks().create_task.assert_called_once_with(
        {
            "data": {
                "projects": ["techs_project_gid"],
                "section": "section_gid",
                "tags": ["tech_ready_tag"],
                "custom_fields": {
                    "airtable_custom_field_id": "12345",
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
