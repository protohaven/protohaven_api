"""Asana task integration methods"""

import datetime
import json
from functools import lru_cache

from dateutil import parser as dateparser

from protohaven_api.config import get_config, tz, tznow
from protohaven_api.integrations import airtable_base
from protohaven_api.integrations.data.connector import get as get_connector


def _use_db():
    con = get_connector()
    if con is None:
        return False
    return get_connector().db_format() == "nocodb"


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
    if _use_db():
        for rec in airtable_base.get_all_records("tasks", "shop_and_maintenance_tasks"):
            yield (
                rec["fields"]["Name"],
                dateparser.parse(rec["fields"]["UpdatedAt"]).astimezone(tz),
            )
        return

    for t in _tasks().search_tasks_for_workspace(
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
    ):
        yield (t["name"], dateparser.parse(t["modified_at"].astimezone(tz)))


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


def complete(gid):
    """Complete a task"""
    # https://developers.asana.com/reference/updatetask
    return _tasks().update_task({"data": {"completed": True}}, gid, {})


def _get_maint_ref(t):
    """Extracts the "airtable ID" custom field from a maintenance task"""
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

    def _build_map(aid, completed, modified_at, now):
        if not completed:
            result[aid] = now
            return
        mod = dateparser.parse(modified_at)
        if aid not in result or mod > result[aid]:
            result[aid] = mod

    now = tznow()

    if _use_db():
        for t in airtable_base.get_all_records("tasks", "shop_and_maintenance_tasks"):
            _build_map(
                t["fields"]["Maint Ref"],
                t["fields"]["Completed"],
                t["fields"]["UpdatedAt"],
                now,
            )
        return result

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
        _build_map(_get_maint_ref(t), t["completed"], t["modified_at"], now)
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

    if _use_db():
        status, result = airtable_base.insert_records(
            [
                {
                    "Tool Report": True,
                    "Priority": "P0" if urgent else None,
                    "Name": name,
                    "Notes": notes,
                }
            ],
            "tasks",
            "shop_and_maintenance_tasks",
        )
        print(result)
        return result[0]["Id"]

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


@lru_cache(maxsize=1)
def _resolve_section_gid(section):
    """Gets a mapping of Asana section names to their ID's"""
    for r in _sections().get_sections_for_project(
        get_config("asana/shop_and_maintenance_tasks/gid"), {}
    ):
        if r["name"].lower().strip() == section.lower().strip():
            return r["gid"]
    return None


# Could also create tech task for maintenance here
def add_maintenance_task_if_not_exists(name, notes, maint_ref, level, section=None):
    """Add a task to the shop tech asana project if it doesn't already exist"""

    if _use_db():
        for rec in airtable_base.get_all_records("tasks", "shop_and_maintenance_tasks"):
            if (
                rec["fields"]["Maint Ref"] == maint_ref
                and not rec["fields"]["completed"]
            ):
                return rec["Id"]
        _, result = airtable_base.insert_records(
            [
                {
                    "Name": name,
                    "Notes": notes,
                    "Maint Ref": maint_ref,
                    "Level": level,
                    "Section": section,
                }
            ],
            "tasks",
            "shop_and_maintenance_tasks",
        )
        return result[0]["Id"]

    if section is not None:
        section = _resolve_section_gid(section)

    matching = list(
        _tasks().search_tasks_for_workspace(
            get_config("asana/gid"),
            {
                f"custom_fields.{get_config('asana/shop_and_maintenance_tasks/custom_fields/airtable_id/gid')}.value": maint_ref,  # pylint: disable=line-too-long
                "completed": False,
                "limit": 1,
            },
        )
    )
    if len(matching) > 0:
        return matching[0].get("gid")  # Already exists

    tag_ids = get_config("asana/shop_and_maintenance_tasks/tags")
    tags = [tag_ids[level]]  # tags MUST have a lookup ID
    result = _tasks().create_task(
        {
            "data": {
                "projects": [get_config("asana/shop_and_maintenance_tasks/gid")],
                "section": section,
                "tags": tags,
                "custom_fields": {
                    get_config(
                        "asana/shop_and_maintenance_tasks/custom_fields/airtable_id/gid"
                    ): str(maint_ref),
                },
                "name": name,
                "notes": notes,
            }
        },
        {},
    )
    # print(result)
    task_gid = result.get("gid")
    if section and task_gid:
        _sections().add_task_for_section(
            str(section), {"body": {"data": {"task": task_gid}}}
        )
    return task_gid
