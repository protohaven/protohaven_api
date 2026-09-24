"""Registry of all Cronicle QA jobs."""

from dataclasses import dataclass
from typing import Callable

from protohaven_api.qa import jobs
from protohaven_api.qa.base import QAContext


@dataclass(frozen=True)
class JobSpec:
    """A single runnable QA job."""

    name: str
    category: str
    fn: Callable[[QAContext], None]
    destructive: bool = False


def _specs():
    return [
        JobSpec("probe_events", "probers", jobs.probers.test_probe_events),
        JobSpec("probe_homepage", "probers", jobs.probers.test_probe_homepage),
        JobSpec("sign_ins", "readonly", jobs.readonly.test_tech_sign_ins),
        JobSpec(
            "check_doors",
            "readonly",
            jobs.readonly.test_check_door_sensors,
        ),
        JobSpec(
            "check_empty_shifts",
            "readonly",
            jobs.readonly.test_check_empty_shifts,
        ),
        JobSpec(
            "donations_summary",
            "readonly",
            jobs.readonly.test_donation_requests,
        ),
        JobSpec("check_cameras", "readonly", jobs.readonly.test_check_cameras),
        JobSpec("class_emails", "readonly", jobs.readonly.test_class_emails),
        JobSpec(
            "instructor_apps",
            "readonly",
            jobs.readonly.test_instructor_applications,
        ),
        JobSpec(
            "private_instruction",
            "readonly",
            jobs.readonly.test_private_instruction,
        ),
        JobSpec(
            "private_instruction_daily",
            "readonly",
            jobs.readonly.test_daily_private_instruction,
        ),
        JobSpec(
            "shop_tech_apps",
            "readonly",
            jobs.readonly.test_shop_tech_applications,
        ),
        JobSpec("square_txns", "readonly", jobs.readonly.test_square_txns),
        JobSpec("membership_val", "readonly", jobs.readonly.test_membership_val),
        JobSpec("instructor_sched", "readonly", jobs.readonly.test_instructor_sched),
        JobSpec("recertification", "readonly", jobs.readonly.test_recertification),
        JobSpec("phone_msgs", "asana_tasks", jobs.asana_tasks.test_phone_messages),
        JobSpec(
            "project_requests",
            "asana_tasks",
            jobs.asana_tasks.test_project_requests,
        ),
        JobSpec(
            "maint_tasks_noop",
            "asana_tasks",
            jobs.asana_tasks.test_gen_maintenance_tasks_noop,
        ),
        JobSpec("backup_wiki", "additive", jobs.additive.test_backup_wiki),
        JobSpec(
            "backup_neon_accounts",
            "additive",
            jobs.additive.test_backup_neon_accounts,
        ),
        JobSpec(
            "backup_neon_events",
            "additive",
            jobs.additive.test_backup_neon_events,
        ),
        JobSpec("backup_sheets", "additive", jobs.additive.test_backup_sheets),
        JobSpec(
            "sync_booked_members",
            "additive",
            jobs.additive.test_sync_booked_members,
        ),
        JobSpec(
            "restock_discounts",
            "additive",
            jobs.additive.test_restock_discounts,
        ),
        JobSpec(
            "sync_clearances",
            "additive",
            jobs.additive.test_sync_clearances,
        ),
        JobSpec(
            "discord_nick",
            "destructive",
            jobs.destructive.test_discord_nick,
            destructive=True,
        ),
        JobSpec(
            "discord_role",
            "destructive",
            jobs.destructive.test_discord_role,
            destructive=True,
        ),
        JobSpec(
            "init_memberships",
            "destructive",
            jobs.destructive.test_init_memberships,
            destructive=True,
        ),
        JobSpec(
            "cleanup_orphaned_class_reservations",
            "destructive",
            jobs.destructive.test_cleanup_orphaned_class_reservations,
            destructive=True,
        ),
    ]


ALL_JOBS = _specs()


def get_job(name: str) -> JobSpec | None:
    """Return the job spec matching `name`, if it exists."""
    for spec in ALL_JOBS:
        if spec.name == name:
            return spec
    return None


def jobs_by_category():
    """Return mapping of category to ordered list of job specs."""
    result: dict[str, list[JobSpec]] = {}
    for spec in ALL_JOBS:
        result.setdefault(spec.category, []).append(spec)
    return result
