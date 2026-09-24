"""QA tests for additive Cronicle jobs."""

# pylint: disable=missing-function-docstring

import datetime
import functools
import logging
import re

from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, airtable_base, booked, drive, neon
from protohaven_api.qa.base import (
    QAContext,
    assert_log_contains,
    assert_no_comms_sent,
    assert_sent_discord,
)
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

    # Register the generated Booked user for cleanup if the job created one.
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


def test_sync_tools(ctx: QAContext):
    result = ctx.run(
        "sync_reservable_tools",
        "elvv9mdlx2j",
        f"--no-apply --filter=qa-no-such-tool-{ctx.run_id}",
        send_comms=True,
    )
    assert result.code == 0
    assert_no_comms_sent(result)


def test_post_classes(ctx: QAContext):
    result = ctx.run(
        "post_classes_to_neon",
        "elzk399t7ph",
        f"--no-apply --ovr=qa-no-such-schedule-{ctx.run_id}",
        send_comms=True,
    )
    assert result.code == 0
    assert_no_comms_sent(result)


def test_refresh_volunteer_memberships(ctx: QAContext):
    result = ctx.run(
        "refresh_volunteer_memberships",
        "em8x5gxfp4t",
        f"--no-apply --filter=qa-no-such-neon-{ctx.run_id} --limit=1",
        send_comms=True,
    )
    assert result.code == 0
    assert_no_comms_sent(result)


def test_policy_enforcement(ctx: QAContext):
    result = ctx.run(
        "enforce_policies",
        "elzd1jx39n8",
        "--no-apply",
        send_comms=True,
    )
    assert result.code == 0


def test_sync_clearances(ctx: QAContext):
    result = ctx.run(
        "sync_clearances",
        "em8x5c0o24r",
        f"--no-apply --filter_users={neon_fixture.QA_EMAIL_PREFIX}qa@protohaven.org",
        send_comms=True,
    )
    assert result.code == 0
    assert_no_comms_sent(result)
