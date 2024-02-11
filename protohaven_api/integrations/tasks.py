"""Asana task integration methods"""

from functools import cache

from dateutil import parser as dateparser

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector

cfg = get_config()["asana"]


def _sections():
    """Fetches the sections API client via the connector module"""
    return get_connector().asana_sections()


def _tasks():
    """Fetches the asana client via the connector module"""
    return get_connector().asana_tasks()


def _projects():
    """Fetches the projets API client via connector"""
    return get_connector().asana_projects()


def get_all_projects():
    """Get all projects in the Protohaven workspace"""
    return _projects().get_projects_for_workspace(cfg["gid"], {}, opt_pretty=True)


def get_tech_ready_tasks(modified_before):
    """Get tasks assigned to techs"""
    # https://developers.asana.com/reference/gettasksforproject
    return _tasks().search_tasks_for_workspace(
        cfg["gid"],
        {
            "projects.all": cfg["techs_project"],
            "completed": False,
            "modified_on.before": modified_before.strftime("%Y-%m-%d"),
            "tags.all": cfg["tech_ready_tag"],
            "opt_fields": ",".join(
                [
                    "name",
                    "modified_at",
                    "custom_fields.name",
                    "custom_fields.number_value",
                    "custom_fields.text_value",
                ]
            ),
        },
    )


def get_project_requests():
    """Get project requests submitted by members & nonmembers"""
    # https://developers.asana.com/reference/gettasksforproject
    return _tasks().get_tasks_for_project(
        cfg["project_requests"],
        {
            "opt_fields": ",".join(["completed", "notes", "name"]),
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
        "opt_fields": ",".join(
            [
                "completed",
                "name",
                "memberships.section",
                "created_at",
                "modified_at",
            ]
        ),
    }
    for t in _tasks().get_tasks_for_project(cfg["purchase_requests"], opts):
        t2 = aggregate(t)
        if t2:
            yield t2
    for t in _tasks().get_tasks_for_project(cfg["class_supply_requests"], opts):
        t2 = aggregate(t)
        if t2:
            yield t2


def complete(gid):
    """Complete a task"""
    # https://developers.asana.com/reference/updatetask
    return _tasks().update_task(gid, {"completed": True})


def get_shop_tech_maintenance_section_map():
    """Gets a mapping of Asana section names to their ID's"""
    result = _sections().get_sections_for_project(cfg["techs_project"], {})
    return {r["name"]: r["gid"] for r in result}


# Could also create tech task for maintenance here
def add_maintenance_task_if_not_exists(name, desc, airtable_id, section_gid=None):
    """Add a task to the shop tech asana project if it doesn't already exist"""
    matching = _tasks().search_tasks_for_workspace(
        cfg["gid"],
        {
            f"custom_fields.{cfg['custom_field_airtable_id']}.value": airtable_id,
            "completed": False,
            "limit": 1,
        },
    )
    if len(list(matching)) > 0:
        return False  # Already exists

    result = _tasks().create_task(
        {
            "data": {
                "projects": [cfg["techs_project"]],
                "section": section_gid,
                "tags": [cfg["tech_ready_tag"]],
                "custom_fields": {
                    cfg["custom_field_airtable_id"]: str(airtable_id),
                },
                "name": name,
                "notes": desc,
            }
        },
        {},
    )
    # print(result)
    task_gid = result.get("gid")
    if section_gid and task_gid:
        _sections().add_task_for_section(
            str(section_gid), {"body": {"data": {"task": task_gid}}}
        )
    return True


if __name__ == "__main__":
    # for task in get_open_purchase_requests():
    #    print(task)
    #    break
    #
    from protohaven_api.integrations.data.connector import init as init_connector

    init_connector(dev=False)
    for n, _ in get_shop_tech_maintenance_section_map().items():
        print(n)
