"""Manages maintenance tasks - scheduling new ones, notifying techs etc."""

import datetime
import logging

from protohaven_api.config import get_config, tznow
from protohaven_api.integrations import comms, tasks, wiki

log = logging.getLogger("maintenance.manager")

REQUIRED_FIELDS = (
    "maint_ref",
    "maint_task",
    "maint_level",
    "maint_freq_days",
)


def _task_label(m):
    """Return a human-readable label for a wiki maintenance task, even
    when some identifying tags are missing."""
    return (
        f"{m.get('book_slug', 'unknown book')}/"
        f"{m.get('page_slug', 'unknown page')} "
        f"(task {m.get('maint_task', 'unknown')!r}, "
        f"ref {m.get('maint_ref', 'unknown')!r})"
    )


def _wiki_record_to_candidate(m):
    """Convert one Bookstack maintenance record into a scheduling candidate.

    Returns None for unapproved records. Raises KeyError when required
    tags are missing and ValueError when maint_freq_days is not an integer.
    """
    if not (m.get("approval_state") or {}).get("approved_revision"):
        return None

    missing = [k for k in REQUIRED_FIELDS if k not in m or m[k] in (None, "")]
    if missing:
        raise KeyError(f"missing Bookstack tag(s): {', '.join(missing)}")

    try:
        freq = int(m["maint_freq_days"])
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"maint_freq_days must be an integer, got {m['maint_freq_days']!r}"
        ) from e

    return {
        "id": m["maint_ref"],
        "origin": "Bookstack",
        "name": m["maint_task"],
        "detail": (
            f"See https://wiki.protohaven.org/books/{m['book_slug']}/page/"
            f"{m['page_slug']}"
        ),
        "level": m["maint_level"],
        "freq": freq,
        "section": m.get("maint_asana_section"),
    }


def get_maintenance_needed_tasks(now=None):
    """Fetches a list of recurring tasks from Bookstack that are due to be
    scheduled into asana for action.

    "Due"-ness is determined by the last completion of an Asana task with the same
    reference to the origin of that task.
    """
    if not now:
        now = tznow()

    log.info("Loading maintenance completion dates")
    last_completions = tasks.last_maintenance_completion_map()
    log.info(f"{len(last_completions.keys())} tasks with known last completion dates")

    log.info("Loading candidate tasks from Bookstack wiki")
    candidates = []
    errors = []
    for book in get_config("bookstack/maintenance/books"):
        for m in wiki.get_maintenance_data(book):
            try:
                candidate = _wiki_record_to_candidate(m)
            except (KeyError, TypeError, ValueError) as e:
                log.error(f"Skipping malformed maintenance task {_task_label(m)}: {e}")
                errors.append(f"- {_task_label(m)}: {e}")
                continue
            if candidate is not None:
                candidates.append(candidate)

    if errors:
        comms.send_discord_message(
            "Errors when loading maintenance tasks from Bookstack:\n"
            + "\n".join(errors),
            "#tech-automation",
            blocking=False,
        )

    log.info(f"Loaded {len(candidates)} task(s)")

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
