"""Asana task integration methods"""

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
    return _tasks().get_tasks_for_project(
        cfg["project_requests"],
        {
            "opt_fields": ",".join(["completed", "notes", "name"]),
        },
    )


def get_private_instruction_requests():
    """Get instruction requests submitted by members"""
    return _tasks().get_tasks_for_project(
        cfg["private_instruction_requests"],
        {
            "opt_fields": ",".join(["completed", "notes", "name", "created_at"]),
        },
    )


def get_instructor_applicants(exclude_on_hold=False, exclude_complete=False):
    """Get applications for instructor position that aren't completed"""
    onhold_id = cfg["instructor_applicants"]["on_hold_section"]
    for req in _tasks().get_tasks_for_project(
        cfg["instructor_applicants"]["gid"],
        {
            "opt_fields": ",".join(["completed", "name", "memberships.section"]),
        },
    ):
        if exclude_complete and req.get("completed"):
            continue
        if exclude_on_hold and onhold_id in [
            m.get("section", {}).get("gid") for m in req.get("memberships", [])
        ]:
            continue
        yield req


def get_shop_tech_applicants(exclude_on_hold=False, exclude_complete=False):
    """Get applications for shop tech position that aren't completed"""
    onhold_id = cfg["shop_tech_applicants"]["on_hold_section"]
    for req in _tasks().get_tasks_for_project(
        cfg["shop_tech_applicants"]["gid"],
        {
            "opt_fields": ",".join(["completed", "name", "memberships.section"]),
        },
    ):
        if exclude_complete and req.get("completed"):
            continue
        if exclude_on_hold and onhold_id in [
            m.get("section", {}).get("gid") for m in req.get("memberships", [])
        ]:
            continue
        yield req


def get_phone_messages():
    """Get all uncompleted phone messages"""
    return _tasks().get_tasks_for_project(
        cfg["phone_messages"],
        {
            "opt_fields": ",".join(["completed", "name", "notes", "created_at"]),
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
    return _tasks().update_task({"data": {"completed": True}}, gid, {})


def get_shop_tech_maintenance_section_map():
    """Gets a mapping of Asana section names to their ID's"""
    result = _sections().get_sections_for_project(cfg["techs_project"], {})
    return {r["name"]: r["gid"] for r in result}


# Could also create tech task for maintenance here
def add_maintenance_task_if_not_exists(name, desc, airtable_id, section_gid=None):
    """Add a task to the shop tech asana project if it doesn't already exist"""
    matching = list(
        _tasks().search_tasks_for_workspace(
            cfg["gid"],
            {
                f"custom_fields.{cfg['custom_field_airtable_id']}.value": airtable_id,
                "completed": False,
                "limit": 1,
            },
        )
    )
    if len(matching) > 0:
        return matching[0].get("gid")  # Already exists

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
    return task_gid
