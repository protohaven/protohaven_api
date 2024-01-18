"""Asana task integration methods"""

from functools import cache

from dateutil import parser as dateparser

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector

cfg = get_config()["asana"]


@cache
def client():
    """Fetches the asana client via the connector module"""
    get_connector().asana_client()


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


# Could also create tech task for maintenance here

if __name__ == "__main__":
    for task in get_open_purchase_requests():
        print(task)
        break
