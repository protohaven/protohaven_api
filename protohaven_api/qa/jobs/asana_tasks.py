"""QA tests for jobs that complete Asana tasks."""

# pylint: disable=missing-function-docstring

import datetime
import os

from protohaven_api.automation.maintenance import manager
from protohaven_api.config import tznow
from protohaven_api.qa.base import (
    QA_CHANNEL,
    QAContext,
    assert_log_contains,
    assert_marked_complete,
    assert_sent_discord,
    assert_sent_email,
)
from protohaven_api.qa.fixtures import asana as asana_fixture


def test_project_requests(ctx: QAContext):
    notes = (
        "Project Description:\n"
        "QA Cronicle project request\n"
        "Materials Budget: 100\n"
        f"Deadline for Project Completion:\n{(tznow() + datetime.timedelta(days=7)).isoformat()}\n"
    )
    gid = asana_fixture.create_task(
        "project_requests",
        f"QA Cronicle project request {ctx.run_id}",
        notes,
        ctx,
    )
    result = ctx.run(
        "project_requests",
        "elth9zp5g01",
        f"--apply --filter_gid={gid}",
        send_comms=True,
    )
    assert_sent_discord(result)
    assert_marked_complete(result, gid)


def test_phone_messages(ctx: QAContext):
    notes = (
        "QA Cronicle phone message\n"
        "Please return my call.\n"
        "Name: QA Tester\n"
        "Phone: 555-0000\n"
    )
    gid = asana_fixture.create_task(
        "phone_messages",
        f"QA Cronicle phone message {ctx.run_id}",
        notes,
        ctx,
    )
    result = ctx.run(
        "phone_messages",
        "elw7tkk5n4v",
        f"--apply --filter_gid={gid}",
        send_comms=True,
    )
    assert_sent_email(result)
    assert_marked_complete(result, gid)


def test_gen_maintenance_tasks(ctx: QAContext):
    """Exercise maintenance-task scheduling safely with a non-matching filter.

    Maintenance candidates originate from Bookstack rather than Airtable, and
    there is no safe create/delete API for Bookstack tags. A scoped filter run
    verifies the command's filter and no-apply path without creating real Asana
    tasks.
    """
    old_chan_ovr = os.environ.get("CHAN_OVERRIDE")
    os.environ["CHAN_OVERRIDE"] = QA_CHANNEL
    try:
        candidates = manager.get_maintenance_needed_tasks()
    finally:
        if old_chan_ovr is None:
            os.environ.pop("CHAN_OVERRIDE", None)
        else:
            os.environ["CHAN_OVERRIDE"] = old_chan_ovr
    if candidates:
        candidate_id = candidates[0]["id"]
        filt = candidate_id
        expected = "Found 1 needed maintenance tasks"
    else:
        filt = f"qa-no-such-task-{ctx.run_id}"
        expected = "Found 0 needed maintenance tasks"

    result = ctx.run(
        "gen_maintenance_tasks",
        "eltiobjj002",
        f"--no-apply --filter={filt} --num=1",
        send_comms=True,
    )
    assert result.code == 0
    assert_log_contains(result.text, [expected])
    assert_sent_discord(result)
