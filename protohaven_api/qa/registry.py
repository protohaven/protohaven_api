"""Registry of all Cronicle QA jobs."""

from dataclasses import dataclass, field
from typing import Any, Callable

from protohaven_api.qa import jobs
from protohaven_api.qa.base import QAContext


@dataclass(frozen=True)
class JobSpec:
    """A single runnable QA job."""

    # pylint: disable=too-many-instance-attributes

    name: str
    category: str
    fn: Callable[[QAContext], None]
    event_id: str
    args: str = ""
    send_comms: bool = False
    dm: bool = False
    params: dict[str, Any] = field(default_factory=dict)
    destructive: bool = False


def _specs():
    return [
        JobSpec(
            "probe_events", "probers", jobs.probers.test_probe_events, "em3xcyglgdj"
        ),
        JobSpec(
            "probe_homepage", "probers", jobs.probers.test_probe_homepage, "em403g0czew"
        ),
        JobSpec(
            "sign_ins",
            "readonly",
            jobs.readonly.test_tech_sign_ins,
            "elzn07uwhqg",
            send_comms=True,
        ),
        JobSpec(
            "check_doors",
            "readonly",
            jobs.readonly.test_check_door_sensors,
            "em5wzj6552l",
            send_comms=True,
        ),
        JobSpec(
            "check_empty_shifts",
            "readonly",
            jobs.readonly.test_check_empty_shifts,
            "emryv0nravu",
            send_comms=True,
        ),
        JobSpec(
            "donations_summary",
            "readonly",
            jobs.readonly.test_donation_requests,
            "em78dbzj04f",
            send_comms=True,
        ),
        JobSpec(
            "check_cameras",
            "readonly",
            jobs.readonly.test_check_cameras,
            "em5d0rdob1l",
            send_comms=True,
        ),
        JobSpec(
            "class_emails",
            "readonly",
            jobs.readonly.test_class_emails,
            "elwnkuoqf8g",
            send_comms=True,
        ),
        JobSpec(
            "instructor_apps",
            "readonly",
            jobs.readonly.test_instructor_applications,
            "elwnqdz2o8j",
            send_comms=True,
        ),
        JobSpec(
            "private_instruction",
            "readonly",
            jobs.readonly.test_private_instruction,
            "elzadpyaqmj",
            send_comms=True,
        ),
        JobSpec(
            "private_instruction_daily",
            "readonly",
            jobs.readonly.test_daily_private_instruction,
            "elziy4cxkp4",
            send_comms=True,
        ),
        JobSpec(
            "shop_tech_apps",
            "readonly",
            jobs.readonly.test_shop_tech_applications,
            "elw7tf3bg4s",
            send_comms=True,
        ),
        JobSpec(
            "square_txns",
            "readonly",
            jobs.readonly.test_square_txns,
            "elw7tp2fs4x",
            send_comms=True,
        ),
        JobSpec(
            "membership_val",
            "readonly",
            jobs.readonly.test_membership_val,
            "elxbtcrmq3d",
            send_comms=True,
        ),
        JobSpec(
            "instructor_sched",
            "readonly",
            jobs.readonly.test_instructor_sched,
            "em1zpa3989p",
            send_comms=True,
        ),
        JobSpec(
            "recertification",
            "readonly",
            jobs.readonly.test_recertification,
            "emitg0mgfzf",
            send_comms=True,
        ),
        JobSpec(
            "phone_msgs",
            "asana_tasks",
            jobs.asana_tasks.test_phone_messages,
            "elw7tkk5n4v",
            send_comms=True,
        ),
        JobSpec(
            "project_requests",
            "asana_tasks",
            jobs.asana_tasks.test_project_requests,
            "elth9zp5g01",
            send_comms=True,
        ),
        JobSpec(
            "maint_tasks",
            "additive",
            jobs.asana_tasks.test_gen_maintenance_tasks,
            "eltiobjj002",
            send_comms=True,
        ),
        JobSpec(
            "sync_tools",
            "additive",
            jobs.additive.test_sync_tools,
            "elvv9mdlx2j",
            send_comms=True,
        ),
        JobSpec(
            "post_classes",
            "additive",
            jobs.additive.test_post_classes,
            "elzk399t7ph",
            send_comms=True,
        ),
        JobSpec(
            "policy_enforcement",
            "additive",
            jobs.additive.test_policy_enforcement,
            "elzd1jx39n8",
            send_comms=True,
        ),
        JobSpec(
            "refresh_volunteer_memberships",
            "additive",
            jobs.additive.test_refresh_volunteer_memberships,
            "em8x5gxfp4t",
            send_comms=True,
        ),
        JobSpec(
            "backup_wiki",
            "additive",
            jobs.additive.test_backup_wiki,
            "em4u369ldgl",
            send_comms=True,
        ),
        JobSpec(
            "backup_neon_accounts",
            "additive",
            jobs.additive.test_backup_neon_accounts,
            "emssampvlg3",
            send_comms=True,
        ),
        JobSpec(
            "backup_neon_events",
            "additive",
            jobs.additive.test_backup_neon_events,
            "emssb5u1vg9",
            send_comms=True,
        ),
        JobSpec(
            "backup_sheets",
            "additive",
            jobs.additive.test_backup_sheets,
            "emss9yewlg0",
            send_comms=True,
        ),
        JobSpec(
            "sync_booked_members",
            "additive",
            jobs.additive.test_sync_booked_members,
            "em5ahun5604",
            send_comms=True,
        ),
        JobSpec(
            "restock_discounts",
            "additive",
            jobs.additive.test_restock_discounts,
            "em6fgimj413",
            send_comms=True,
        ),
        JobSpec(
            "sync_clearances",
            "additive",
            jobs.additive.test_sync_clearances,
            "em8x5c0o24r",
            send_comms=True,
        ),
        JobSpec(
            "discord_nick",
            "destructive",
            jobs.destructive.test_discord_nick,
            "elzx3nvdvu4",
            send_comms=True,
            dm=True,
            destructive=True,
        ),
        JobSpec(
            "discord_role",
            "destructive",
            jobs.destructive.test_discord_role,
            "elzsp1fmpsk",
            send_comms=True,
            dm=True,
            destructive=True,
        ),
        JobSpec(
            "init_memberships",
            "destructive",
            jobs.destructive.test_init_memberships,
            "em1zpg3sc9r",
            send_comms=True,
            destructive=True,
        ),
        JobSpec(
            "cleanup_orphaned_class_reservations",
            "destructive",
            jobs.destructive.test_cleanup_orphaned_class_reservations,
            "emmtkylp1m7",
            send_comms=True,
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


def all_event_ids() -> set[str]:
    """Return the set of Cronicle event IDs covered by the registry."""
    return {spec.event_id for spec in ALL_JOBS}
