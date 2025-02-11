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

    log.info("Loading maintenance completion dates")
    last_completions = tasks.last_maintenance_completion_map()
    log.info(f"{len(last_completions.keys())} tasks with known last completion dates")

    log.info("Loading candidate tasks from Bookstack wiki")
    candidates = [
        {
            "id": m["maint_ref"],
            "origin": "Bookstack",
            "name": m["maint_task"],
            "detail": (
                f"See https://wiki.protohaven.org/books/{m['book_slug']}/pages/"
                f"{m['page_slug']}/{m['approval_state']['approved_id']}"
            ),
            "tags": [m["maint_level"]],
            "freq": int(m["maint_freq_days"]),
            "section": section_map.get(m.get("maint_asana_section")),
        }
        for book in get_config("bookstack/maintenance/books")
        for m in wiki.get_maintenance_data(book)
        if m["approval_state"].get("approved_revision")
    ]
    log.info(f"Loaded {len(candidates)} task(s)")
    log.info("Loading candidate tasks from Airtable recurring tasks table")
    candidates += [
        {
            "id": t["id"],
            "origin": "Airtable",
            "name": t["fields"]["Task Name"],
            "detail": t["fields"]["Task Detail"],
            "freq": int(t["fields"]["Frequency"]),
            "tags": [t["fields"]["Skill Level"]],
            "section": section_map.get(t["fields"]["Asana Section"]),
        }
        for t in airtable.get_all_maintenance_tasks()
        if "REVIEW NEEDED" not in t["fields"]["Skill Level"]
    ]
    log.info(f"Loaded {len(candidates)} total task(s)")

    needed = []
    for c in candidates:
        log.debug(f"{c['origin']} Task {c['id']}: {c['name']}")
        last_scheduled = last_completions.get(c["id"])
        log.debug(f"{c['id']} last scheduled: {last_scheduled}")
        next_schedule = (
            last_scheduled + datetime.timedelta(days=c["freq"])
            if last_scheduled is not None
            else now
        )
        if next_schedule <= now:
            needed.append(
                {**c, "last_scheduled": last_scheduled, "next_schedule": next_schedule}
            )
            log.debug(f"Append {c}")
        else:
            log.debug(f"Skip (too early)\t{c}")
    return needed


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
