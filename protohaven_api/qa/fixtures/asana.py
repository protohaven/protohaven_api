"""Asana QA fixture helpers."""

from protohaven_api.config import get_config
from protohaven_api.integrations import tasks
from protohaven_api.integrations.data.connector import get as get_connector
from protohaven_api.qa.base import QAContext


def _project_gid(project: str) -> str:
    cfg = get_config("asana")[project]
    return cfg["gid"] if isinstance(cfg, dict) else cfg


def create_task(
    project: str,
    name: str,
    notes: str = "",
    ctx: QAContext | None = None,
) -> str:
    """Create an Asana task in a configured project.

    If `ctx` is provided, cleanup is registered to complete the task.
    """
    gid = _project_gid(project)
    result = (
        get_connector()
        .asana_tasks()
        .create_task(
            {"data": {"projects": [gid], "name": name, "notes": notes}},
            {},
        )
    )
    task_gid = result.get("gid")
    if not task_gid:
        raise RuntimeError(f"Failed to create Asana task in {project}: {result}")
    if ctx is not None:
        ctx.cleanup.register(
            f"complete Asana task {task_gid}", lambda: tasks.complete(task_gid)
        )
    return task_gid
