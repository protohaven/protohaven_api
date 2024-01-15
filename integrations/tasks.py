import asana
from dateutil import parser as dateparser

from config import get_config

cfg = get_config()["asana"]

client = asana.Client.access_token(cfg["token"])


def get_all_projects():
    return client.projects.get_projects_for_workspace(cfg["gid"], {}, opt_pretty=True)


def get_tech_tasks():
    # https://developers.asana.com/reference/gettasksforproject
    return client.tasks.get_tasks_for_project(
        cfg["techs_project"],
        {
            "opt_fields": [
                "completed",
                "custom_fields.name",
                "custom_fields.number_value",
                "custom_fields.text_value",
            ],
            "limit": 10,  # TODO remove
        },
    )


def get_project_requests():
    # https://developers.asana.com/reference/gettasksforproject
    return client.tasks.get_tasks_for_project(
        cfg["project_requests"],
        {
            "opt_fields": ["completed", "notes", "name"],
        },
    )


def get_open_purchase_requests():
    # https://developers.asana.com/reference/gettasksforproject
    def aggregate(t):
        if t["completed"]:
            return
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
    for t in client.tasks.get_tasks_for_project(cfg["purchase_requests"], opts):
        t2 = aggregate(t)
        if t2:
            yield t2
    for t in client.tasks.get_tasks_for_project(cfg["class_supply_requests"], opts):
        t2 = aggregate(t)
        if t2:
            yield t2


def complete(gid):
    # https://developers.asana.com/reference/updatetask
    return client.tasks.update_task(gid, dict(completed=True))


# TODO create tech task for maintenance

if __name__ == "__main__":
    # for project in get_all_projects():
    #    print(project)
    # for task in get_tech_tasks():
    #    print(task)
    for task in get_open_purchase_requests():
        print(task)
        break
