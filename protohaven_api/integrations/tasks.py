"""Asana task integration methods"""

from functools import cache

from dateutil import parser as dateparser

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector

cfg = get_config()["asana"]


@cache
def client():
    """Fetches the asana client via the connector module"""
    return get_connector().asana_client()


def get_all_projects():
    """Get all projects in the Protohaven workspace"""
    return client().projects.get_projects_for_workspace(cfg["gid"], {}, opt_pretty=True)


def get_tech_tasks():
    """Get tasks assigned to techs"""
    # https://developers.asana.com/reference/gettasksforproject
    return client().tasks.get_tasks_for_project(
        cfg["techs_project"],
        {
            "opt_fields": [
                "completed",
                "custom_fields.name",
                "custom_fields.number_value",
                "custom_fields.text_value",
            ],
        },
    )


def get_project_requests():
    """Get project requests submitted by members & nonmembers"""
    # https://developers.asana.com/reference/gettasksforproject
    return client().tasks.get_tasks_for_project(
        cfg["project_requests"],
        {
            "opt_fields": ["completed", "notes", "name"],
        },
    )


def get_open_purchase_requests():
    """Get purchase requests made by techs & instructors"""

    # https://developers.asana.com/reference/gettasksforproject
    def aggregate(t):
        if t["completed"]:
            return None
        cats = {
            cfg["purchase_low_priority_section"]: "low_pri",
            cfg["purchase_high_priority_section"]: "high_pri",
            cfg["purchase_on_hold_section"]: "on_hold",
            cfg["class_supply_default_section"]: "class_supply",
        }
        t["category"] = "unknown"
        for mem in t["memberships"]:
            cat = cats.get(mem["section"]["gid"])
            if cat is not None:
                t["category"] = cat
                break
        for tk in ("created_at", "modified_at"):
            t[tk] = dateparser.parse(t[tk])
        return t

    opts = {
        "opt_fields": [
            "completed",
            "name",
            "memberships.section",
            "created_at",
            "modified_at",
        ],
    }
    for t in client().tasks.get_tasks_for_project(cfg["purchase_requests"], opts):
        t2 = aggregate(t)
        if t2:
            yield t2
    for t in client().tasks.get_tasks_for_project(cfg["class_supply_requests"], opts):
        t2 = aggregate(t)
        if t2:
            yield t2


def complete(gid):
    """Complete a task"""
    # https://developers.asana.com/reference/updatetask
    return client().tasks.update_task(gid, {"completed": True})


def get_shop_tech_maintenance_section_map():
    result = client().sections.get_sections_for_project(cfg["techs_project"])
    return {r["name"]: r["gid"] for r in result}


# Could also create tech task for maintenance here
def add_maintenance_task_if_not_exists(name, desc, airtable_id, section_gid=None):
    """Add a task to the shop tech asana project if it doesn't already exist"""
    matching = client().tasks.search_tasks_for_workspace(
        cfg["gid"],
        {
            f"custom_fields.{cfg['custom_field_airtable_id']}.value": airtable_id,
            "completed": False,
            "limit": 1,
        },
    )
    if len(list(matching)) > 0:
        return False  # Already exists

    result = client().tasks.create_task(
        {
            "projects": [cfg["techs_project"]],
            "section": section_gid,
            "tags": [cfg["tech_ready_tag"]],
            "custom_fields": {
                cfg["custom_field_airtable_id"]: str(airtable_id),
            },
            "name": name,
            "notes": desc,
        }
    )
    # print(result)
    task_gid = result.get("gid")
    if section_gid and task_gid:
        client().sections.add_task_for_section(str(section_gid), {"task": task_gid})
    return True


if __name__ == "__main__":
    # for task in get_open_purchase_requests():
    #    print(task)
    #    break
    #
    from protohaven_api.integrations.data.connector import init as init_connector

    init_connector(dev=False)
    # upsert_maintenance_task("test task; please ignore", 'test description', section_gid=1204501947520301)
    for name, _ in get_shop_tech_maintenance_section_map().items():
        print(name)
