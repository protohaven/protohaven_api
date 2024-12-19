"""Manages maintenance tasks - scheduling new ones, notifying techs etc."""
import datetime
import logging

from dateutil import parser as dateparser

from protohaven_api.config import get_config, tz, tznow
from protohaven_api.integrations import airtable, tasks, wiki

log = logging.getLogger("maintenance.manager")


def get_maintenance_needed_tasks(now=None):
    """Fetches a list of recurring tasks from Airtable and Bookstack that are due to be
    scheduled into asana for action.

    "Due"-ness is determined by the last completion of an Asana task with the same
    reference to the origin of that task.
    """
    if not now:
        now = tznow()

    log.info("Loading maintenance sections")
    section_map = tasks.get_shop_tech_maintenance_section_map()
    log.info(f"{len(section_map.keys())} sections loaded")

    log.info("Loading maintenance completions")
    last_completions = tasks.last_maintenance_completion_map()
    log.info(f"{len(last_completions.keys())} completion(s) loaded")
    for k, v in last_completions.items():
        print(k, v)

    log.info("Loading candidates from wiki & airtable")
    candidates = [
        {
            "id": m["maint_ref"],
            "origin": "Bookstack",
            "name": m["maint_task"],
            "detail": f"See https://wiki.protohaven.org/books/{m['book_slug']}/pages/{m['page_slug']}/{m['approval_state']['approved_id']}",
            "freq": m["maint_freq_days"],
            "section": section_map.get(m.get("maint_asana_section")),
        }
        for m in wiki.get_maintenance_data(get_config("bookstack/basic_maint_slug"))
        if m["approval_state"].get("approved_revision")
    ] + [
        {
            "id": t["id"],
            "origin": "Airtable",
            "name": t["fields"]["Task Name"],
            "freq": t["fields"]["Frequency"],
            "section": section_map.get(t["fields"]["Asana Section"]),
        }
        for t in airtable.get_all_maintenance_tasks()
    ]

    needed = []
    for c in candidates:
        log.debug(f"{c['origin']} Task {c['id']}: {c['name']}")
        last_scheduled = last_completions.get(c["id"])
        next_schedule = (
            last_scheduled + datetime.timedelta(days=c["freq"])
            if last_scheduled
            else now
        )
        if next_schedule <= now:
            needed.append(
                {**c, "last_scheduled": last_scheduled, "next_schedule": next_schedule}
            )
            log.debug(f"APPEND\t{c['name']}")
        else:
            log.debug(f"SKIP_TOO_EARLY\t{c['name']}")
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
