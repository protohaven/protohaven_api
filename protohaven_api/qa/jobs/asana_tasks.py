"""QA tests for jobs that complete Asana tasks."""

import datetime

from protohaven_api.config import tznow
from protohaven_api.qa.base import (
    QAContext,
    assert_marked_complete,
    assert_no_comms_sent,
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


def test_gen_maintenance_tasks_noop(ctx: QAContext):
    """Sanity-check the maintenance task scheduler with a no-op filter."""
    result = ctx.run(
        "gen_maintenance_tasks",
        "eltiobjj002",
        f"--no-apply --filter=qa-no-such-task-{ctx.run_id} --num=1",
        send_comms=True,
    )
    assert result.code == 0
    assert_no_comms_sent(result)
