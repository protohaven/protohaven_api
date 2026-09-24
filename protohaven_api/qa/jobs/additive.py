"""QA tests for additive Cronicle jobs."""

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
    drive,
    eventbrite,
    neon,
)
from protohaven_api.integrations.models import Role
from protohaven_api.qa.base import (
    QAContext,
    assert_log_contains,
    assert_no_comms_sent,
    assert_sent_discord,
    assert_sent_email,
)
from protohaven_api.qa.fixtures import airtable as airtable_fixture
from protohaven_api.qa.fixtures import booked as booked_fixture
from protohaven_api.qa.fixtures import neon as neon_fixture

log = logging.getLogger("qa.additive")

BACKUP_EVENTS = {
    "backup_wiki": "em4u369ldgl",
    "backup_neon_accounts": "emssampvlg3",
    "backup_neon_events": "emssb5u1vg9",
    "backup_sheets": "emss9yewlg0",
}


def _require_drive_folder(ctx: QAContext):
    if not ctx.drive_folder_id:
        raise RuntimeError("QA Drive folder ID is required for backup jobs")


def _register_uploaded_files_from_log(ctx: QAContext, text: str):
    for file_id in re.findall(r"Uploaded, id ([\w-]+)", text):
        ctx.cleanup.register(
            f"delete Drive file {file_id}",
            functools.partial(_delete_drive_file, file_id),
        )


def _delete_drive_file(file_id: str):
    drive.delete_file(file_id)


def _test_backup_job(ctx: QAContext, name: str):
    _require_drive_folder(ctx)
    result = ctx.run(
        name,
        BACKUP_EVENTS[name],
        f"--apply --parent_id={ctx.drive_folder_id}",
        send_comms=True,
    )
    assert result.code == 0
    assert_log_contains(result.text, ["Uploaded, id"])
    _register_uploaded_files_from_log(ctx, result.text)
    assert_sent_discord(result)


def test_backup_wiki(ctx: QAContext):
    _test_backup_job(ctx, "backup_wiki")


def test_backup_neon_accounts(ctx: QAContext):
    _test_backup_job(ctx, "backup_neon_accounts")


def test_backup_neon_events(ctx: QAContext):
    _test_backup_job(ctx, "backup_neon_events")


def test_backup_sheets(ctx: QAContext):
    _test_backup_job(ctx, "backup_sheets")


def test_sync_booked_members(ctx: QAContext):
    acct = neon_fixture.create_mock_account(ctx, "sync-booked-members")
    start = tznow()
    end = start + datetime.timedelta(days=30)
    neon.create_zero_cost_membership(acct.neon_id, start, end)

    result = ctx.run(
        "sync_booked_members",
        "em5ahun5604",
        f"--include={acct.email} --apply",
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_discord(result)
    assert_log_contains(result.text, [f"associated with neon #{acct.neon_id}"])

    for user in booked.get_all_users():
        if user.email.lower() == acct.email.lower():
            ctx.cleanup.register(
                f"delete Booked user {user.id}",
                functools.partial(booked.delete_user, user.id),
            )
            break


def test_restock_discounts(ctx: QAContext):
    before = {
        r["id"] for r in airtable_base.get_all_records("class_automation", "discounts")
    }
    cur_qty = airtable.get_num_valid_unassigned_coupons(
        tznow() + datetime.timedelta(days=30)
    )
    result = ctx.run(
        "restock_discounts",
        "em6fgimj413",
        (
            f"--no-apply --limit=2 --target_qty={cur_qty + 2} "
            "--coupon_amount=1 --remaining_days_valid=30 --expiration_days=90"
        ),
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_discord(result)
    assert_log_contains(
        result.text,
        ["Creating the following coupons", "pushed to airtable"],
    )
    after = {
        r["id"] for r in airtable_base.get_all_records("class_automation", "discounts")
    }
    for rec_id in after - before:
        ctx.cleanup.register(
            f"delete Airtable coupon {rec_id}",
            functools.partial(
                airtable_base.delete_record,
                "class_automation",
                "discounts",
                rec_id,
            ),
        )


def _area_and_exclusions():
    air_areas = {
        a["fields"]["Name"] for a in airtable.get_areas() if a["fields"].get("Name")
    }
    booked_groups = {k.replace("&amp;", "&") for k in booked.get_resource_group_map()}
    common = air_areas & booked_groups
    assert common, "No shared Airtable/Booked area available"
    area = next(iter(common))
    return area, ",".join(sorted(air_areas - {area}))


def test_sync_tools(ctx: QAContext):
    area, exclusions = _area_and_exclusions()
    preflight = ctx.run(
        "sync_reservable_tools",
        "elvv9mdlx2j",
        f"--no-apply --filter=qa-no-such-tool --exclude_areas={exclusions}",
        send_comms=False,
    )
    assert preflight.code == 0

    tool_code = f"QA-{ctx.run_id.upper()[:8]}"
    resource = booked_fixture.create_resource(ctx, f"QA tool {ctx.run_id}")
    airtable_fixture.create_tool_record(
        ctx,
        tool_code=tool_code,
        tool_name=f"QA tool {ctx.run_id}",
        area=area,
        booked_resource_id=resource,
    )

    dry = ctx.run(
        "sync_reservable_tools",
        "elvv9mdlx2j",
        f"--no-apply --filter={tool_code} --exclude_areas={exclusions}",
        send_comms=False,
    )
    assert dry.code == 0
    assert_log_contains(dry.text, ["Change "])

    applied = ctx.run(
        "sync_reservable_tools",
        "elvv9mdlx2j",
        f"--apply --filter={tool_code} --exclude_areas={exclusions}",
        send_comms=True,
    )
    assert applied.code == 0
    assert_log_contains(applied.text, ["Change "])
    assert_sent_discord(applied)


def _copyable_eventbrite_row():
    for row in airtable.get_class_automation_schedule_raw():
        f = row["fields"]
        if (
            f.get("Class")
            and f.get("Instructor")
            and f.get("Sessions")
            and f.get("Eventbrite (from Class)")
        ):
            return row
    raise AssertionError("No Eventbrite-enabled class schedule row to copy")


def test_post_classes(ctx: QAContext):
    raw = _copyable_eventbrite_row()
    start = (tznow() + datetime.timedelta(days=30)).replace(
        hour=18, minute=0, second=0, microsecond=0
    )
    fields = dict(raw["fields"])
    fields.update(
        {
            "Neon ID": "",
            "Event ID": "",
            "Sessions": start.isoformat(),
            "Confirmed": tznow().isoformat(),
            "Rejected": "",
            "Name": f"QA Cronicle Post Classes {ctx.run_id}",
        }
    )
    rec_id = airtable_fixture.create_schedule_row(ctx, fields)

    result = ctx.run(
        "post_classes_to_neon",
        "elzk399t7ph",
        (
            f"--apply --ovr={rec_id} --no-publish --no-registration "
            "--no-reserve --no-discounts"
        ),
        send_comms=True,
    )
    assert result.code == 0
    assert_log_contains(result.text, ["Event #", "created"])
    match = re.search(r"Event #([\w]+) created", result.text)
    assert match, "Could not identify created Eventbrite event ID"
    eventbrite_id = match.group(1)
    ctx.cleanup.register(
        f"delete Eventbrite event {eventbrite_id}",
        lambda: eventbrite.delete_event_unsafe(eventbrite_id),
    )
    row = airtable.get_scheduled_class(rec_id)
    assert str(row.event_id) == str(eventbrite_id)
    assert_sent_email(result)
    assert_sent_discord(result)


def test_refresh_volunteer_memberships(ctx: QAContext):
    acct = neon_fixture.create_mock_account(ctx, "refresh-volunteer-memberships")
    neon.patch_member_role(acct.neon_id, Role.SHOP_TECH, True)
    now = tznow()
    neon_fixture.create_membership(
        acct.neon_id,
        now,
        now + datetime.timedelta(days=1),
        level={"id": 19, "name": "Shop Tech"},
        term={"id": 61, "name": "Shop Tech"},
    )

    result = ctx.run(
        "refresh_volunteer_memberships",
        "em8x5gxfp4t",
        f"--apply --filter={acct.neon_id} --limit=1",
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_discord(result)
    assert_log_contains(result.text, ["volunteer_refresh_summary"])


def test_policy_enforcement(ctx: QAContext):
    acct = neon_fixture.create_mock_account(ctx, "policy-enforcement")
    before_fees = {
        r["id"] for r in airtable.get_policy_fees() if r["fields"].get("Created")
    }
    new_violation_id = airtable_fixture.create_violation(
        ctx,
        acct.neon_id,
        daily_fee=5,
        onset=tznow() - datetime.timedelta(hours=2),
    )
    fee_violation_id = airtable_fixture.create_violation(
        ctx,
        acct.neon_id,
        daily_fee=5,
        onset=tznow() - datetime.timedelta(days=2),
    )
    result = ctx.run(
        "enforce_policies",
        "elzd1jx39n8",
        f"--apply --filter={new_violation_id},{fee_violation_id}",
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_email(result)
    assert_sent_discord(result)
    assert_log_contains(
        result.text,
        [
            "violation_started",
            "violation_ongoing",
            "enforcement_summary",
        ],
    )
    after_fees = {
        r["id"] for r in airtable.get_policy_fees() if r["fields"].get("Created")
    }
    for rec in airtable.get_policy_fees():
        rec_id = rec["id"]
        if rec_id in before_fees or rec_id not in after_fees:
            continue
        violation_links = rec["fields"].get("Violation") or []
        if isinstance(violation_links, str):
            violation_links = [violation_links]
        if fee_violation_id not in violation_links:
            continue
        ctx.cleanup.register(
            f"delete policy_enforcement/fees record {rec_id}",
            functools.partial(
                airtable_base.delete_record,
                "policy_enforcement",
                "fees",
                rec_id,
            ),
        )


def test_sync_clearances(ctx: QAContext):
    result = ctx.run(
        "sync_clearances",
        "em8x5c0o24r",
        "--no-apply --filter_users=hello+qa-testing@protohaven.org",
        send_comms=True,
    )
    assert result.code == 0
    assert_no_comms_sent(result)
