"""Automation for merging info from Airtable and Asana"""
from protohaven_api.integrations import airtable, tasks


def get_open_tasks_matching_tool(record_id, tool_name):
    """Fetches all open tasks matching a given tool record, including
    fuzzy matches by the tool name."""

    # Tasks in Asana are tagged with the Airtable record that generated them.
    # We have to map these based on whether they're associated with the tool's
    # record ID.
    task_record_ids = {
        t["fields"]["id"]
        for t in airtable.get_all_maintenance_tasks()
        if record_id in t["fields"].get("Tool/Area")
    }

    tool_name = tool_name.strip().lower()
    for t in tasks.get_all_open_maintenance_tasks():
        if (
            tool_name in t["name"].lower()
            or tasks.get_airtable_id(t) in task_record_ids
        ):
            yield {"name": t["name"], "modified_at": t["modified_at"], "uri": t["uri"]}
