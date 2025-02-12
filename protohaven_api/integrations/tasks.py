"""Asana task integration methods"""

import datetime
import json

from dateutil import parser as dateparser

from protohaven_api.config import get_config, tznow
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
            "projects.all": get_config("asana/shop_and_maintenance_tasks/gid"),
            "completed": False,
            "modified_on.before": modified_before.strftime("%Y-%m-%d"),
            "tags.all": get_config("asana/shop_and_maintenance_tasks/tags/tech_ready"),
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


def get_with_onhold_section(project, exclude_on_hold=False, exclude_complete=False):
    """Gets a list of tasks in the project, optionally filtering by completion state
    or presence in an "On Hold" section"""
    cfg = get_config("asana")[project]
    for req in _tasks().get_tasks_for_project(
        cfg["gid"],
        {
            "opt_fields": ",".join(["completed", "name", "memberships.section"]),
        },
    ):
        if exclude_complete and req.get("completed"):
            continue
        if exclude_on_hold and cfg["on_hold_section"] in [
            m.get("section", {}).get("gid") for m in req.get("memberships", [])
        ]:
            continue
        yield req


def get_donation_requests(exclude_complete=False):
    """Get requests for donations"""
    return get_with_onhold_section(
        "donation_requests",
        exclude_on_hold=False,
        exclude_complete=exclude_complete,
    )


def get_instructor_applicants(exclude_on_hold=False, exclude_complete=False):
    """Get applications for instructor position that aren't completed"""
    return get_with_onhold_section(
        "instructor_applicants", exclude_on_hold, exclude_complete
    )


def get_shop_tech_applicants(exclude_on_hold=False, exclude_complete=False):
    """Get applications for shop tech position that aren't completed"""
    return get_with_onhold_section(
        "shop_tech_applicants", exclude_on_hold, exclude_complete
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
    result = _sections().get_sections_for_project(
        get_config("asana/shop_and_maintenance_tasks/gid"), {}
    )
    return {r["name"]: r["gid"] for r in result}


def get_all_open_maintenance_tasks():
    """Fetches all uncompleted tasks matching a tool record in Airtable"""
    return _tasks().search_tasks_for_workspace(
        get_config("asana/gid"),
        {
            "completed": False,
            "limit": 100,
            "opt_fields": ",".join(
                [
                    "name",
                    "modified_at",
                    "uri",
                    "custom_fields.name",
                    "custom_fields.number_value",
                    "custom_fields.text_value",
                ]
            ),
        },
    )


def get_airtable_id(t):
    """Extracts the airtable ID custom field from a task"""
    for cf in t["custom_fields"]:
        if cf["name"] == "Airtable Record":
            return cf["text_value"]
    return None


def last_maintenance_completion_map():
    """Builds a map of origin IDs to the last completion date.
    Returns the current time for all incomplete tasks.

    Tasks completed earlier than 400 days ago are excluded.
    """
    result = {}
    now = tznow()
    for t in _tasks().get_tasks_for_project(
        get_config("asana/shop_and_maintenance_tasks/gid"),
        {
            # Python Asana lib is auto-paginated
            # See https://forum.asana.com/t/pagination-using-python/38930
            # We use completed_since to prevent excessive loading of super old tasks
            # since there's no way to order fetch by time data
            "completed_since": (now - datetime.timedelta(days=400)).isoformat(),
            "opt_fields": ",".join(
                [
                    "completed",
                    "name",
                    "modified_at",
                    "uri",
                    "custom_fields.name",
                    "custom_fields.number_value",
                    "custom_fields.text_value",
                ]
            ),
        },
    ):
        aid = get_airtable_id(t)
        if not t["completed"]:
            result[aid] = now
            continue
        mod = dateparser.parse(t["modified_at"])
        if aid not in result or mod > result[aid]:
            result[aid] = mod
    return result


def add_tool_report_task(  # pylint: disable=too-many-arguments
    tools, summary, status, images, reporter, urgent=False
):
    """Adds a tool report to the asana maintenance project"""
    s = summary.replace("\n", " ")
    name = f"{', '.join(tools)} - {s}"
    name = name.replace("<", "&lt;").replace(">", "&gt;")
    notes = (
        f"{status}\nImages: {json.dumps(images)}\n"
        f"Report created by {reporter} via Airtable form"
    )
    notes = notes.replace("<", "&lt;").replace(">", "&gt;")

    custom_fields = {}
    if urgent:
        custom_fields[
            get_config("asana/shop_and_maintenance_tasks/custom_fields/priority/gid")
        ] = get_config(
            "asana/shop_and_maintenance_tasks/custom_fields/priority/values/p0"
        )

    result = _tasks().create_task(
        {
            "data": {
                "projects": [get_config("asana/shop_and_maintenance_tasks/gid")],
                "tags": [
                    get_config("asana/shop_and_maintenance_tasks/tags/tool_report")
                ],
                "custom_fields": custom_fields,
                "name": name,
                "html_notes": f"<body>{notes}</body>",
            }
        },
        {},
    )
    return result.get("gid")


# Could also create tech task for maintenance here
def add_maintenance_task_if_not_exists(name, desc, airtable_id, tags, section_gid=None):
    """Add a task to the shop tech asana project if it doesn't already exist"""
    matching = list(
        _tasks().search_tasks_for_workspace(
            get_config("asana/gid"),
            {
                f"custom_fields.{get_config('asana/shop_and_maintenance_tasks/custom_fields/airtable_id/gid')}.value": airtable_id,  # pylint: disable=line-too-long
                "completed": False,
                "limit": 1,
            },
        )
    )
    if len(matching) > 0:
        return matching[0].get("gid")  # Already exists

    tag_ids = get_config("asana/shop_and_maintenance_tasks/tags")
    tags = [tag_ids[t] for t in tags]  # tags MUST have a lookup ID
    result = _tasks().create_task(
        {
            "data": {
                "projects": [get_config("asana/shop_and_maintenance_tasks/gid")],
                "section": section_gid,
                "tags": tags,
                "custom_fields": {
                    get_config(
                        "asana/shop_and_maintenance_tasks/custom_fields/airtable_id/gid"
                    ): str(airtable_id),
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
