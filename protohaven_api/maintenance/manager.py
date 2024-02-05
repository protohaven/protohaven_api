import datetime
import logging

import pytz
from dateutil import parser as dateparser

from protohaven_api.integrations import airtable, tasks

tz = pytz.timezone("EST")
log = logging.getLogger("maintenance.manager")


def get_maintenance_needed_tasks(now=None):
    if not now:
        now = datetime.datetime.now().astimezone(tz)
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
        now = datetime.datetime.now().astimezone(tz)
    for t in tt:
        log.info(f"Applying {t['id']} {t['name']} section {t['section']}")
        if not tasks.add_maintenance_task_if_not_exists(
            t["name"], t["detail"], t["id"], section_gid=t["section"]
        ):
            log.debug("Task already inserted")
        rep = airtable.update_recurring_task_date(t["id"], now)
        if rep.status_code != 200:
            raise Exception(rep.content)


if __name__ == "__main__":
    from protohaven_api.integrations.data.connector import init as init_connector

    init_connector(dev=False)
    logging.basicConfig(level=logging.INFO)
    tt = get_maintenance_needed_tasks()
    log.info(f"Found {len(tt)} needed maintenance tasks")
    tt.sort(key=lambda t: t["next_schedule"])
    apply_maintenance_tasks(tt[:5])
    log.info("Done")
    # for t in get_maintenance_needed_tasks():
    #    print(t)
