"""QA tests for read-only Cronicle jobs."""

# pylint: disable=missing-function-docstring,too-many-lines,too-many-locals
# pylint: disable=too-many-arguments,unused-argument

import datetime
import logging

from protohaven_api.automation.techs import techs as forecast
from protohaven_api.config import safe_parse_datetime, tznow
from protohaven_api.integrations import airtable, neon, neon_base
from protohaven_api.integrations.data.neon import CustomField
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


def _event_args_names(args: str) -> list[str]:
    """Extract positional names from a Cronicle ARGS string."""
    toks = args.replace("=", " ").split()
    # Drop known --flags and their values; keep bare words.
    flags = {
        "--now",
        "--start",
        "--days-ahead",
        "--urgent-days",
        "--planning-days",
        "--no-dedupe",
        "--apply",
        "--no-apply",
    }
    names = []
    for tok in toks:
        if tok in flags or tok.startswith("--"):
            continue
        if tok.startswith("-"):
            continue
        names.append(tok)
    return names


def _assert_conditional_comms(result):
    assert result.code == 0
    if (
        "Nothing to report" in result.text
        or "No empty shifts found" in result.text
        or "was empty, so nothing to do." in result.text
    ):
        assert_no_comms_sent(result)
    else:
        assert_sent_discord(result)


def test_check_door_sensors(ctx: QAContext):
    args = ctx.event_args("em5wzj6552l")
    result = ctx.run(
        "check_door_sensors",
        "em5wzj6552l",
        args,
        send_comms=True,
    )
    for name in _event_args_names(args):
        assert_log_contains(result.text, [name])
    _assert_conditional_comms(result)


def test_check_cameras(ctx: QAContext):
    args = ctx.event_args("em5d0rdob1l")
    result = ctx.run(
        "check_cameras",
        "em5d0rdob1l",
        args,
        send_comms=True,
    )
    for name in _event_args_names(args):
        assert_log_contains(result.text, [name])
    _assert_conditional_comms(result)


def _first_shift_with_people(now, exclude=None):
    exclude = exclude or set()
    for day in forecast.generate(now, 7, include_pii=True)["calendar_view"]:
        for ap, hour in (("AM", 11), ("PM", 17)):
            if (day["date"], ap) in exclude:
                continue
            people = day[ap]["people"]
            if people and not day["is_holiday"]:
                when = safe_parse_datetime(day["date"]).replace(
                    hour=hour, minute=0, second=0, microsecond=0
                )
                return day, ap, people, when
    return None


def _first_empty_shift(now, exclude=None):
    exclude = exclude or set()
    for day in forecast.generate(now, 7, include_pii=True)["calendar_view"]:
        for ap in ("AM", "PM"):
            if (day["date"], ap) in exclude:
                continue
            if not day[ap]["people"] and not day["is_holiday"]:
                when = safe_parse_datetime(day["date"]).replace(
                    hour=11 if ap == "AM" else 17, minute=0, second=0, microsecond=0
                )
                return day, ap, when
    return None


def _force_empty_shift(ctx: QAContext, day, ap, people) -> None:
    airtable_fixture.create_empty_shift_override(
        ctx,
        day["date"],
        ap,
        [p.name for p in people],
    )


def _shift_when(now, day, ap):
    return safe_parse_datetime(day["date"]).replace(
        hour=11 if ap == "AM" else 17, minute=0, second=0, microsecond=0
    )


def test_tech_sign_ins(ctx: QAContext):
    now = tznow()
    found = _first_shift_with_people(now)
    assert found, "No non-holiday tech shift with people found"
    day, ap, people, when = found
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
    assert_no_comms_sent(result)

    # Alert case: use a nearby empty shift, forcing one if necessary.
    empty = _first_empty_shift(now, exclude={(day["date"], ap)})
    if empty is None:
        target = None
        for d in forecast.generate(now, 7, include_pii=True)["calendar_view"]:
            for a in ("AM", "PM"):
                if (d["date"], a) == (day["date"], ap):
                    continue
                if d[a]["people"] and not d["is_holiday"]:
                    target = (d, a, d[a]["people"])
                    break
            if target:
                break
        assert target, "No shift available to force empty for alert case"
        target_day, target_ap, target_people = target
        _force_empty_shift(ctx, target_day, target_ap, target_people)
        when = _shift_when(now, target_day, target_ap)
    else:
        _, _, when = empty

    result = ctx.run(
        "tech_sign_ins",
        "elzn07uwhqg",
        f"--now={when.isoformat()}",
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_discord(result)
    assert_log_contains(result.text, ["shift_no_techs"])


def test_check_empty_shifts(ctx: QAContext):
    now = tznow()
    empty = _first_empty_shift(now)
    if empty is not None:
        day, ap, _ = empty
    else:
        found = _first_shift_with_people(now)
        assert found, "No shift available to force empty"
        day, ap, people, _ = found
        _force_empty_shift(ctx, day, ap, people)

    result = ctx.run(
        "check_empty_shifts",
        "emryv0nravu",
        (
            f"--start={day['date']} --days-ahead=1 --urgent-days=1 "
            "--planning-days=1 --no-dedupe"
        ),
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_discord(result)
    assert_log_contains(result.text, ["empty_shift_techs"])


def _copyable_schedule_row():
    for row in airtable.get_class_automation_schedule_raw():
        f = row["fields"]
        if f.get("Class") and f.get("Instructor") and f.get("Sessions"):
            return row
    raise AssertionError("No existing Airtable class schedule row to copy")


def _create_class_event(
    ctx: QAContext,
    scenario: str,
    *,
    days_out: int,
    supply_state: str | None = None,
    attendees: int = 0,
    capacity: int = 6,
):
    """Create an unpublished Neon event + matching Airtable schedule row."""
    raw = _copyable_schedule_row()
    start = (tznow() + datetime.timedelta(days=days_out)).replace(
        hour=18, minute=0, second=0, microsecond=0
    )
    end = start + datetime.timedelta(hours=3)
    name = f"QA Cronicle Class Emails {scenario} {ctx.run_id}"
    event_id = neon_base.create_event(
        name,
        "Temporary QA event; will be deleted automatically.",
        start,
        end,
        dry_run=False,
        published=False,
        registration=attendees > 0,
        free=True,
    )
    assert event_id
    ctx.cleanup.register(
        f"delete Neon event {event_id}",
        lambda: neon_base.delete_event_unsafe(event_id),
    )

    if attendees:
        ticket_id = neon.fetch_event(
            event_id, tickets=True
        ).single_registration_ticket_id
        assert ticket_id
        for i in range(attendees):
            acct = neon_fixture.create_mock_account(ctx, f"class-emails-{scenario}-{i}")
            neon_fixture.register_for_event(ctx, acct.neon_id, event_id, ticket_id)

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
    if supply_state is not None:
        fields["Supply State"] = supply_state
    airtable_fixture.create_schedule_row(ctx, fields)
    return event_id


def _run_class_emails(ctx: QAContext, event_id: str):
    return ctx.run(
        "gen_class_emails",
        "elwnkuoqf8g",
        f"--filter={event_id} --no-published_only",
        send_comms=True,
    )


def test_class_emails(ctx: QAContext):
    scenarios = [
        ("LOW_ATTENDANCE_7DAYS", 5, None, 0, 6, ["instructor_low_attendance"]),
        (
            "SUPPLY_CHECK_NEEDED",
            8,
            "Supply Check Needed",
            0,
            6,
            ["instructor_check_supplies"],
        ),
        (
            "CONFIRM",
            1,
            None,
            1,
            6,
            ["instructor_class_confirmed", "registrant_class_confirmed"],
        ),
        (
            "CANCEL",
            1,
            None,
            0,
            6,
            ["instructor_class_canceled", "registrant_class_canceled"],
        ),
        ("FOR_TECHS", 1, None, 2, 10, ["tech_openings"]),
        (
            "POST_RUN_SURVEY",
            -2,
            None,
            1,
            6,
            ["instructor_log_reminder", "registrant_post_class_survey"],
        ),
    ]
    for scenario, days_out, supply_state, attendees, capacity, needles in scenarios:
        event_id = _create_class_event(
            ctx,
            scenario,
            days_out=days_out,
            supply_state=supply_state,
            attendees=attendees,
            capacity=capacity,
        )
        result = _run_class_emails(ctx, event_id)
        assert result.code == 0
        assert_log_contains(result.text, needles)
        if scenario == "FOR_TECHS":
            assert_sent_discord(result)
        else:
            assert_sent_email(result)


def _mock_asana_task(ctx, project, name, notes=""):
    return asana_fixture.create_task(project, name, notes, ctx)


def test_donation_requests(ctx: QAContext):
    name = f"QA Cronicle donation request {ctx.run_id}"
    gid = _mock_asana_task(ctx, "donation_requests", name)
    result = ctx.run(
        "donation_requests",
        "em78dbzj04f",
        f"--filter_gid={gid}",
        send_comms=True,
    )
    assert_sent_discord(result)
    assert_log_contains(result.text, [name.split(",", maxsplit=1)[0]])


def test_instructor_applications(ctx: QAContext):
    name = f"QA Cronicle instructor applicant {ctx.run_id}"
    gid = _mock_asana_task(ctx, "instructor_applicants", name)
    result = ctx.run(
        "instructor_applications",
        "elwnqdz2o8j",
        f"--filter_gid={gid}",
        send_comms=True,
    )
    assert_sent_discord(result)
    assert_log_contains(result.text, [name.split(",", maxsplit=1)[0]])


def test_shop_tech_applications(ctx: QAContext):
    name = f"QA Cronicle shop tech applicant {ctx.run_id}"
    gid = _mock_asana_task(ctx, "shop_tech_applicants", name)
    result = ctx.run(
        "shop_tech_applications",
        "elw7tf3bg4s",
        f"--filter_gid={gid}",
        send_comms=True,
    )
    assert_sent_discord(result)
    assert_log_contains(result.text, [name.split(",", maxsplit=1)[0]])


def _private_instruction_notes(ctx, tag):
    return (
        "Details: QA private instruction request\n"
        "Availability: Immediately\n"
        "Name: QA Tester\n"
        "Email: hello+qa-testing@protohaven.org\n"
        "Phone: 555-0000\n"
        f"Tag: {tag}\n"
    )


def test_private_instruction(ctx: QAContext):
    name = f"QA Cronicle private instruction {ctx.run_id}"
    gid = _mock_asana_task(
        ctx,
        "private_instruction_requests",
        name,
        _private_instruction_notes(ctx, "weekly"),
    )
    result = ctx.run(
        "private_instruction",
        "elzadpyaqmj",
        f"--filter_gid={gid} --summary_limit=300",
        send_comms=True,
    )
    assert_sent_email(result)
    assert_sent_discord(result)


def test_daily_private_instruction(ctx: QAContext):
    name = f"QA Cronicle daily private instruction {ctx.run_id}"
    gid = _mock_asana_task(
        ctx,
        "private_instruction_requests",
        name,
        _private_instruction_notes(ctx, "daily"),
    )
    result = ctx.run(
        "private_instruction",
        "elziy4cxkp4",
        f"--daily --filter_gid={gid} --summary_limit=300",
        send_comms=True,
    )
    assert_sent_discord(result)


def test_square_txns(ctx: QAContext):
    result = ctx.run(
        "square_txns",
        "elw7tp2fs4x",
        "",
        send_comms=True,
    )
    assert result.code == 0
    assert_log_contains(
        result.text,
        [
            "Fetched",
            "subscription plans",
            "unpaid invoices",
            "Processed",
        ],
    )
    _assert_conditional_comms(result)


def test_membership_val(ctx: QAContext):
    now = tznow()
    ids = []

    # Active membership with no end date.
    acct = neon_fixture.create_mock_account(ctx, "membership-val-no-end")
    neon_fixture.create_membership(acct.neon_id, now, None)
    ids.append(acct.neon_id)

    # Shop Tech membership without the API server role.
    acct = neon_fixture.create_mock_account(ctx, "membership-val-shop-tech")
    neon_fixture.create_membership(
        acct.neon_id,
        now,
        now + datetime.timedelta(days=30),
        level={"id": 19, "name": "Shop Tech"},
        term={"id": 61, "name": "Shop Tech"},
    )
    ids.append(acct.neon_id)

    # AMP income-rate/term mismatch.
    acct = neon_fixture.create_mock_account(ctx, "membership-val-amp")
    neon_base.set_custom_fields(
        acct.neon_id,
        (CustomField.INCOME_BASED_RATE, "Low Income"),
    )
    neon_fixture.create_membership(
        acct.neon_id,
        now,
        now + datetime.timedelta(days=30),
        level={"id": 1, "name": "AMP General"},
        term={"id": 1, "name": "ELI"},
    )
    ids.append(acct.neon_id)

    result = ctx.run(
        "validate_memberships",
        "elxbtcrmq3d",
        f"--member_ids={','.join(ids)}",
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_discord(result)
    assert_log_contains(
        result.text,
        [
            "membership_validation_problems",
            "no end date",
            "Needs role Shop Tech",
            "Mismatch between Income based rate",
        ],
    )


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
    configs = airtable.get_tool_recert_configs_by_code()
    assert configs, "No tool recert configs available"
    tool_code = next(iter(configs))
    past = tznow() - datetime.timedelta(days=30)
    airtable_fixture.create_pending_recert(
        ctx,
        acct.neon_id,
        tool_code,
        past.isoformat(),
        notified=True,
        suspended=False,
    )
    result = ctx.run(
        "recertification",
        "emitg0mgfzf",
        (
            f"--apply --filter_users={acct.neon_id} "
            f"--filter_tool_codes={tool_code} --max_users_affected=1"
        ),
        send_comms=True,
    )
    assert result.code == 0
    assert_sent_email(result)
    assert_sent_discord(result)
    assert_log_contains(result.text, ["member_recert_update", "suspend clearances"])
