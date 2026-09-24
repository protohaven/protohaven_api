"""QA tests for destructive Cronicle jobs."""

# pylint: disable=missing-function-docstring,too-many-lines

import datetime
import functools
import logging
import re

from protohaven_api.config import tznow
from protohaven_api.integrations import (
    airtable,
    airtable_base,
    booked,
    comms,
    neon,
    neon_base,
)
from protohaven_api.integrations.models import Role
from protohaven_api.qa.base import (
    QAContext,
    assert_log_contains,
    assert_sent_discord,
    assert_sent_dm,
    assert_sent_email,
)
from protohaven_api.qa.fixtures import airtable as airtable_fixture
from protohaven_api.qa.fixtures import booked as booked_fixture
from protohaven_api.qa.fixtures import discord as discord_fixture
from protohaven_api.qa.fixtures import neon as neon_fixture

log = logging.getLogger("qa.destructive")


def _active_membership(acct, start=None, end=None):
    start = start or tznow()
    end = end or (start + datetime.timedelta(days=30))
    neon_fixture.create_membership(
        acct.neon_id,
        start,
        end,
        level={"id": 19, "name": "Shop Tech"},
        term={"id": 61, "name": "Shop Tech"},
    )


def test_discord_nick(ctx: QAContext):
    acct = neon_fixture.create_mock_account(ctx, "discord-nick")
    neon.set_discord_user(acct.neon_id, discord_fixture.DISCORD_USER)
    _active_membership(acct)
    discord_fixture.set_nickname(ctx, "QA Old Nickname")

    result = ctx.run(
        "enforce_discord_nicknames",
        "elzx3nvdvu4",
        f"--apply --filter={discord_fixture.DISCORD_USER} --limit=1 --no-warn_not_associated",
        send_comms=True,
        dm=True,
    )
    assert result.code == 0
    assert_sent_discord(result)
    assert_sent_dm(result)
    assert_log_contains(result.text, ["discord_nick_changed"])


def _discord_has_role(role: str) -> bool:
    for member in comms.get_all_members():
        if member[0] == discord_fixture.DISCORD_USER:
            return any(r == role for r, _ in member[3])
    return False


def test_discord_role(ctx: QAContext):
    role = "Techs"
    originally_had_role = _discord_has_role(role)
    if originally_had_role:
        comms.revoke_discord_role(discord_fixture.DISCORD_USER, role)
        ctx.cleanup.register(
            f"restore Discord role {role} to {discord_fixture.DISCORD_USER}",
            lambda: comms.set_discord_role(discord_fixture.DISCORD_USER, role),
        )
    else:
        ctx.cleanup.register(
            f"remove QA-added Discord role {role} from {discord_fixture.DISCORD_USER}",
            lambda: comms.revoke_discord_role(discord_fixture.DISCORD_USER, role),
        )

    acct = neon_fixture.create_mock_account(ctx, "discord-role")
    neon.set_discord_user(acct.neon_id, discord_fixture.DISCORD_USER)
    neon.patch_member_role(acct.neon_id, Role.SHOP_TECH, True)
    _active_membership(acct)

    result = ctx.run(
        "update_role_intents",
        "elzsp1fmpsk",
        (
            f"--filter={discord_fixture.DISCORD_USER} "
            "--apply_records --apply_discord --destructive "
            "--max_users_added=1 --max_users_removed=1"
        ),
        send_comms=True,
        dm=True,
    )
    assert result.code == 0
    assert_sent_dm(result)
    assert_sent_discord(result)
    assert_log_contains(
        result.text, ["Discord role assigned", "discord_role_change_dm"]
    )


def _snapshot_assigned_coupons():
    return {
        r["id"]: r["fields"]
        for r in airtable_base.get_all_records("class_automation", "discounts")
        if r["fields"].get("Assigned")
    }


def test_init_memberships(ctx: QAContext):
    acct = neon_fixture.create_mock_account(ctx, "init-memberships")
    now = tznow()
    neon_fixture.create_membership(
        acct.neon_id,
        now,
        now + datetime.timedelta(days=30),
        level={"id": 1, "name": "General Membership"},
        term={"id": 1, "name": "General - $115/mo (Join)"},
        fee=20,
    )
    before_coupons = _snapshot_assigned_coupons()

    result = ctx.run(
        "init_new_memberships",
        "em1zpg3sc9r",
        f"--apply --filter={acct.neon_id} --limit=1",
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_email(result)
    assert_sent_discord(result)
    assert_log_contains(result.text, ["membership_init_summary"])

    after_coupons = _snapshot_assigned_coupons()
    for rec_id, fields in after_coupons.items():
        original = before_coupons.get(rec_id)
        if original == fields:
            continue
        if original is None:
            original = {"Assigned": "", "Assignee": ""}
        ctx.cleanup.register(
            f"restore Airtable coupon {rec_id}",
            functools.partial(
                airtable_base.update_record,
                {
                    "Assigned": original.get("Assigned", ""),
                    "Assignee": original.get("Assignee", ""),
                },
                "class_automation",
                "discounts",
                rec_id,
            ),
        )


def _copyable_schedule_row():
    for row in airtable.get_class_automation_schedule_raw():
        f = row["fields"]
        if f.get("Class") and f.get("Instructor") and f.get("Sessions"):
            return row
    raise AssertionError("No existing Airtable class schedule row to copy")


def test_cleanup_orphaned_class_reservations(ctx: QAContext):
    raw = _copyable_schedule_row()
    start = (tznow() + datetime.timedelta(days=3)).replace(
        hour=18, minute=0, second=0, microsecond=0
    )
    end = start + datetime.timedelta(hours=3)
    name = f"QA Cronicle Orphaned Reservations {ctx.run_id}"
    event_id = neon_base.create_event(
        name,
        "Temporary QA event; will be deleted automatically.",
        start,
        end,
        dry_run=False,
        published=True,
        registration=False,
        free=True,
    )
    assert event_id
    ctx.cleanup.register(
        f"delete Neon event {event_id}",
        lambda: neon_base.delete_event_unsafe(event_id),
    )

    fields = dict(raw["fields"])
    fields.update(
        {
            "Neon ID": event_id,
            "Sessions": start.isoformat(),
            "Confirmed": tznow().isoformat(),
            "Rejected": "",
            "Name": name,
        }
    )
    airtable_fixture.create_schedule_row(ctx, fields)

    area = (fields.get("Name (from Area) (from Class)") or [None])[0]
    assert area, "No area available on copied schedule row"
    resource_id = booked_fixture.create_resource(
        ctx, f"QA orphan resource {ctx.run_id}"
    )
    booked.apply_resource_custom_fields(resource_id, area=area)

    matching_ref = booked_fixture.reserve(
        ctx,
        resource_id,
        start,
        end,
        title=name,
    )
    assert matching_ref
    orphan_start = start + datetime.timedelta(days=2)
    orphan_ref = booked_fixture.reserve(
        ctx,
        resource_id,
        orphan_start,
        orphan_start + datetime.timedelta(hours=2),
        title="QA orphan reservation",
    )

    preflight = ctx.run(
        "cleanup_orphaned_class_reservations",
        "emmtkylp1m7",
        "--no-apply --max=100 --days=10",
        send_comms=False,
    )
    assert preflight.code == 0
    for ref in re.findall(r"Remove reservation #([\w-]+)", preflight.text):
        if ref != orphan_ref:
            raise RuntimeError(
                f"Real orphan reservation #{ref} found; aborting destructive cleanup"
            )

    result = ctx.run(
        "cleanup_orphaned_class_reservations",
        "emmtkylp1m7",
        "--apply --max=1 --days=10",
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_discord(result)
    assert_log_contains(result.text, [f"Deleted reservation #{orphan_ref}"])
    assert_log_contains(result.text, ["orphaned_reservations_cleanup"])
