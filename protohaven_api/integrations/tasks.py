"""Asana task integration methods"""

from dateutil import parser as dateparser

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector


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
    return _projects().get_projects_for_workspace(
        get_config("asana/gid"), {}, opt_pretty=True
    )


def get_tech_ready_tasks(modified_before):
    """Get tasks assigned to techs"""
    # https://developers.asana.com/reference/gettasksforproject
    return _tasks().search_tasks_for_workspace(
        get_config("asana/gid"),
        {
            "projects.all": get_config("asana/techs_project"),
            "completed": False,
            "modified_on.before": modified_before.strftime("%Y-%m-%d"),
            "tags.all": get_config("asana/tech_ready_tag"),
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
        get_config("asana/project_requests"),
        {
            "opt_fields": ",".join(["completed", "notes", "name"]),
        },
    )


def get_private_instruction_requests():
    """Get instruction requests submitted by members"""
    return _tasks().get_tasks_for_project(
        get_config("asana/private_instruction_requests"),
        {
            "opt_fields": ",".join(["completed", "notes", "name", "created_at"]),
        },
    )


def _get_with_onhold_section(project, exclude_on_hold=False, exclude_complete=False):
    onhold_id = get_config(f"asana/{project}/on_hold_section")
    for req in _tasks().get_tasks_for_project(
        get_config(f"asana/{project}/gid"),
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


def get_instructor_applicants(exclude_on_hold=False, exclude_complete=False):
    """Get applications for instructor position that aren't completed"""
    return _get_with_onhold_section(
        "instructor_applicants", exclude_on_hold, exclude_complete
    )


def get_shop_tech_applicants(exclude_on_hold=False, exclude_complete=False):
    """Get applications for shop tech position that aren't completed"""
    return _get_with_onhold_section(
        "instructor_applicants", exclude_on_hold, exclude_complete
    )


def get_phone_messages():
    """Get all uncompleted phone messages"""
    return _tasks().get_tasks_for_project(
        get_config("asana/phone_messages"),
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
            get_config("asana/purchase_requests/sections")[v]: v
            for v in ("requested", "approved", "ordered", "on_hold")
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
    for t in _tasks().get_tasks_for_project(
        get_config("asana/purchase_requests/gid"), opts
    ):
        t2 = aggregate(t)
        if t2:
            yield t2


def complete(gid):
    """Complete a task"""
    # https://developers.asana.com/reference/updatetask
    return _tasks().update_task({"data": {"completed": True}}, gid, {})


def get_shop_tech_maintenance_section_map():
    """Gets a mapping of Asana section names to their ID's"""
    result = _sections().get_sections_for_project(get_config("asana/techs_project"), {})
    return {r["name"]: r["gid"] for r in result}


# Could also create tech task for maintenance here
def add_maintenance_task_if_not_exists(name, desc, airtable_id, section_gid=None):
    """Add a task to the shop tech asana project if it doesn't already exist"""
    matching = list(
        _tasks().search_tasks_for_workspace(
            get_config("asana/gid"),
            {
                f"custom_fields.{get_config('asana/custom_field_airtable_id')}.value": airtable_id,
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
                "projects": [get_config("asana/techs_project")],
                "section": section_gid,
                "tags": [get_config("asana/tech_ready_tag")],
                "custom_fields": {
                    get_config("asana/custom_field_airtable_id"): str(airtable_id),
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
