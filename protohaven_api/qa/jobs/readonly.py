"""QA tests for read-only Cronicle jobs."""

import datetime
import logging

from protohaven_api.automation.techs import techs as forecast
from protohaven_api.config import safe_parse_datetime, tznow
from protohaven_api.integrations import airtable, neon, neon_base
from protohaven_api.qa.base import (
    QAContext,
    assert_log_contains,
    assert_no_comms_sent,
    assert_sent_discord,
    assert_sent_email,
)
from protohaven_api.qa.fixtures import airtable as airtable_fixture
from protohaven_api.qa.fixtures import asana as asana_fixture
from protohaven_api.qa.fixtures import neon as neon_fixture

log = logging.getLogger("qa.readonly")


def _log_has(result, needle):
    return needle in result.text


def _assert_conditional_comms(result):
    assert result.code == 0
    if "Nothing to report" in result.text or "No empty shifts found" in result.text:
        assert_no_comms_sent(result)
    else:
        assert_sent_discord(result)


def test_check_door_sensors(ctx: QAContext):
    result = ctx.run(
        "check_door_sensors",
        "em5wzj6552l",
        ctx.event_args("em5wzj6552l"),
        send_comms=True,
    )
    _assert_conditional_comms(result)


def test_check_cameras(ctx: QAContext):
    result = ctx.run(
        "check_cameras",
        "em5d0rdob1l",
        ctx.event_args("em5d0rdob1l"),
        send_comms=True,
    )
    _assert_conditional_comms(result)


def test_check_empty_shifts(ctx: QAContext):
    now = tznow()
    result = ctx.run(
        "check_empty_shifts",
        "emryv0nravu",
        (
            f"--start={now.isoformat()} --days-ahead=7 --urgent-days=7 "
            "--planning-days=7 --no-dedupe"
        ),
        send_comms=True,
    )
    _assert_conditional_comms(result)


def _first_shift_with_people(now):
    day = forecast.generate(now, 1, include_pii=True)["calendar_view"][0]
    for ap, hour in (("AM", 11), ("PM", 17)):
        people = day[ap]["people"]
        if people:
            return day, ap, people, now.replace(
                hour=hour, minute=0, second=0, microsecond=0
            )
    return None


def _first_empty_shift(now):
    day = forecast.generate(now, 7, include_pii=True)["calendar_view"][0]
    for ap, hour in (("AM", 11), ("PM", 17)):
        if not day[ap]["people"] and not day["is_holiday"]:
            return now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return None


def test_tech_sign_ins(ctx: QAContext):
    now = tznow()
    found = _first_shift_with_people(now)
    if found:
        _, _, people, when = found
        person = people[0]
        email = person.emails[0]
        airtable_fixture.create_signin(
            ctx,
            email,
            when.isoformat(),
            person.name,
        )
        result = ctx.run(
            "tech_sign_ins",
            "elzn07uwhqg",
            f"--now={when.isoformat()}",
            send_comms=True,
        )
        assert result.code == 0
        # Signed-in shift should not generate a missing-tech alert.
        assert_no_comms_sent(result)
    else:
        log.warning("No on-duty tech shift found; skipping tech_sign_ins QA")


def _create_class_event(ctx: QAContext) -> str:
    """Create a QA Neon class event and matching Airtable schedule row."""
    raw = None
    for row in airtable.get_class_automation_schedule_raw():
        f = row["fields"]
        if f.get("Class") and f.get("Instructor") and f.get("Sessions"):
            raw = row
            break
    assert raw, "No existing Airtable class schedule row to copy"

    starts = [safe_parse_datetime(d) for d in raw["fields"]["Sessions"].split(",")]
    start = starts[0]
    while start < tznow() + datetime.timedelta(days=3):
        start += datetime.timedelta(days=7)
    end = start + datetime.timedelta(hours=3)

    event_id = neon_base.create_event(
        f"QA Cronicle Class Emails {ctx.run_id}",
        "Temporary QA event; will be deleted automatically.",
        start,
        end,
        dry_run=False,
        published=False,
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
            "Name": f"QA Cronicle Class Emails {ctx.run_id}",
        }
    )
    airtable_fixture.create_schedule_row(ctx, fields)
    return event_id


def test_class_emails(ctx: QAContext):
    event_id = _create_class_event(ctx)
    result = ctx.run(
        "gen_class_emails",
        "elwnkuoqf8g",
        f"--filter={event_id} --no-published_only",
        send_comms=True,
    )
    assert result.code == 0
    assert_log_contains(result.text, ["Generated"])


def _mock_asana_task(ctx, project, name, notes=""):
    return asana_fixture.create_task(project, name, notes, ctx)


def test_donation_requests(ctx: QAContext):
    gid = _mock_asana_task(
        ctx,
        "donation_requests",
        f"QA Cronicle donation request {ctx.run_id}",
    )
    result = ctx.run(
        "donation_requests",
        "em78dbzj04f",
        f"--filter_gid={gid}",
        send_comms=True,
    )
    assert_sent_discord(result)


def test_instructor_applications(ctx: QAContext):
    gid = _mock_asana_task(
        ctx,
        "instructor_applicants",
        f"QA Cronicle instructor applicant {ctx.run_id}",
    )
    result = ctx.run(
        "instructor_applications",
        "elwnqdz2o8j",
        f"--filter_gid={gid}",
        send_comms=True,
    )
    assert_sent_discord(result)


def test_shop_tech_applications(ctx: QAContext):
    gid = _mock_asana_task(
        ctx,
        "shop_tech_applicants",
        f"QA Cronicle shop tech applicant {ctx.run_id}",
    )
    result = ctx.run(
        "shop_tech_applications",
        "elw7tf3bg4s",
        f"--filter_gid={gid}",
        send_comms=True,
    )
    assert_sent_discord(result)


def test_private_instruction(ctx: QAContext):
    notes = (
        "Details: QA private instruction request\n"
        "Availability: Immediately\n"
        "Name: QA Tester\n"
        "Email: hello+qa-testing@protohaven.org\n"
        "Phone: 555-0000\n"
    )
    gid = _mock_asana_task(
        ctx,
        "private_instruction_requests",
        f"QA Cronicle private instruction {ctx.run_id}",
        notes,
    )
    result = ctx.run(
        "private_instruction",
        "elzadpyaqmj",
        f"--filter_gid={gid} --summary_limit=300",
        send_comms=True,
    )
    assert_sent_email(result)
    assert_sent_discord(result)


def test_square_txns(ctx: QAContext):
    result = ctx.run(
        "square_txns",
        "elw7tp2fs4x",
        "",
        send_comms=True,
    )
    assert result.code == 0
    assert_log_contains(result.text, ["Processed"])


def test_membership_val(ctx: QAContext):
    acct = neon_fixture.create_mock_account(ctx, "membership-val")
    result = ctx.run(
        "validate_memberships",
        "elxbtcrmq3d",
        f"--member_ids={acct.neon_id}",
        send_comms=True,
    )
    assert result.code == 0
    # A fresh QA account has no valid membership, so validation should report it.
    assert_sent_discord(result)


def test_instructor_sched(ctx: QAContext):
    acct = neon_fixture.create_mock_account(ctx, "instructor-sched")
    airtable_fixture.create_capabilities_row(
        ctx,
        {
            "Neon ID": acct.neon_id,
            "Email": acct.email,
            "Active": True,
        },
    )
    start = tznow() + datetime.timedelta(days=30)
    end = start + datetime.timedelta(days=30)
    result = ctx.run(
        "gen_instructor_schedule_reminder",
        "em1zpa3989p",
        (
            f"--start={start.isoformat()} --end={end.isoformat()} "
            f"--no-require_active --no-require_teachable --filter={acct.email}"
        ),
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_email(result)
    assert_sent_discord(result)


def test_recertification(ctx: QAContext):
    acct = neon_fixture.create_mock_account(ctx, "recertification")
    tool_code = next(iter(airtable.get_tool_recert_configs_by_code()))
    past = tznow() - datetime.timedelta(days=30)
    airtable_fixture.create_pending_recert(
        ctx,
        acct.neon_id,
        tool_code,
        past.isoformat(),
    )
    result = ctx.run(
        "recertification",
        "emitg0mgfzf",
        (
            f"--no-apply --filter_users={acct.neon_id} "
            f"--filter_tool_codes={tool_code} --max_users_affected=1"
        ),
        send_comms=True,
    )
    assert result.code == 0


def test_daily_private_instruction(ctx: QAContext):
    notes = (
        "Details: QA private instruction request\n"
        "Availability: Immediately\n"
        "Name: QA Tester\n"
        "Email: hello+qa-testing@protohaven.org\n"
        "Phone: 555-0000\n"
    )
    gid = _mock_asana_task(
        ctx,
        "private_instruction_requests",
        f"QA Cronicle daily private instruction {ctx.run_id}",
        notes,
    )
    result = ctx.run(
        "private_instruction",
        "elziy4cxkp4",
        f"--daily --filter_gid={gid} --summary_limit=300",
        send_comms=True,
    )
    assert_sent_discord(result)
