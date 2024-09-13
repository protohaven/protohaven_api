"""Manages maintenance tasks - scheduling new ones, notifying techs etc."""
import datetime
import logging

from dateutil import parser as dateparser

from protohaven_api.config import tz, tznow
from protohaven_api.integrations import airtable, tasks

log = logging.getLogger("maintenance.manager")


def get_maintenance_needed_tasks(now=None):
    """Fetches a list of recurring tasks from Airtable that are due to be scheduled
    into asana for action"""
    if not now:
        now = tznow()
    needed = []
    section_map = tasks.get_shop_tech_maintenance_section_map()

    for task in airtable.get_all_maintenance_tasks():
        log.debug(f"Task {task['id']}: {task['fields']['Task Name']}")
        last_scheduled = dateparser.parse(task["fields"]["Last Scheduled"]).astimezone(
            tz
        )
        next_schedule = dateparser.parse(
            task["fields"]["Next Schedule Date"]
        ).astimezone(tz)
        if next_schedule <= now:
            needed.append(
                {
                    "id": task["id"],
                    "last_scheduled": last_scheduled,
                    "next_schedule": next_schedule,
                    "name": task["fields"]["Task Name"],
                    "detail": task["fields"]["Task Detail"],
                    "section": section_map.get(task["fields"]["Asana Section"]),
                }
            )
            log.debug(f"APPEND\t{task['fields']['Task Name']}")
        else:
            log.debug(f"SKIP_TOO_EARLY\t{task['fields']['Task Name']}")
    return needed


def apply_maintenance_tasks(tt, now=None):
    """Applies tasks with data generated from `get_maintenance_needed_tasks`"""
    if not now:
        now = tznow()
    for t in tt:
        log.info(f"Applying {t['id']} {t['name']} section {t['section']}")
        t["gid"] = tasks.add_maintenance_task_if_not_exists(
            t["name"], t["detail"], t["id"], section_gid=t["section"]
        )
        log.info(f"Asana task gid {t.get('gid')} for task {t['id']}")
        status, content = airtable.update_recurring_task_date(t["id"], now)
        if status != 200:
            raise RuntimeError(content)


DEFAULT_STALE_DAYS = 14


def get_stale_tech_ready_tasks(now=None, thresh=DEFAULT_STALE_DAYS):
    """Get tasks in Asana that haven't been acted upon within a certain threshold"""
    if now is None:
        now = tznow()
    thresh = now - datetime.timedelta(days=thresh)
    result = []
    for t in tasks.get_tech_ready_tasks(thresh):
        mod = dateparser.parse(t["modified_at"]).astimezone(tz)
        result.append({"name": t["name"], "days_ago": (now - mod).days})
    return result


def run_daily_maintenance(apply=False, num_to_generate=4):
    """Generates a bounded number of new maintenance tasks per day,
    also looks up stale tasks and creates a summary message for Techs"""
    tt = get_maintenance_needed_tasks()
    log.info(f"Found {len(tt)} needed maintenance tasks")
    tt.sort(key=lambda t: t["next_schedule"])
    tt = tt[:num_to_generate]
    if apply:
        apply_maintenance_tasks(tt)
    else:
        log.warning("skipping application of tasks (apply=False)")
    return tt
