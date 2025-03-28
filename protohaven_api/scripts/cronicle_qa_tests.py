"""Integration tests for Cronicle jobs/events"""

import argparse
import datetime
import logging
import time

import requests

from protohaven_api.config import tznow
from protohaven_api.integrations import airtable, airtable_base, neon_base
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

base_url = None  # pylint: disable=invalid-name
api_key = None  # pylint: disable=invalid-name
REQ_TIMEOUT = 30
JOB_TIMEOUT = 60 * 15

COVR = "#cronicle-automation"
EOVR = "scott@protohaven.org"
DOVR = "@pwacata"


# Disables InsecureRequestWarning spam due to use of `verify=false` in requests
requests.packages.urllib3.disable_warnings()  # pylint: disable=no-member


def cronicle_event_schedule():
    """Fetch schedule of events configured in Cronicle"""
    return requests.get(
        f"{base_url}/api/app/get_schedule/v1",
        headers={"X-API-Key": api_key},
        timeout=REQ_TIMEOUT,
        verify=False,
    ).json()


def run_cronicle_sync(event_id, params):
    """Starts a job on Cronicle"""
    log.info(f"Start {event_id}, params {params}")
    rep = requests.post(
        f"{base_url}/api/app/run_event/v2",
        headers={"X-API-Key": api_key},
        timeout=REQ_TIMEOUT,
        json={"id": event_id, "retries": 0, "timeout": JOB_TIMEOUT, "params": params},
        verify=False,
    ).json()
    if "ids" not in rep:
        raise RuntimeError(rep)
    running = {rid: False for rid in rep["ids"]}
    # log.info(str(rep))
    for rid in running.keys():
        log.info(f"{base_url}#JobDetails?id={rid}")
    while True:
        for rid in running.keys():
            rep = requests.get(
                f"{base_url}/api/app/get_job_status/v1?id={rid}",
                headers={"X-API-Key": api_key},
                timeout=REQ_TIMEOUT,
                verify=False,
            ).json()
            # log.info(str(rep))
            running[rid] = rep["job"].get("complete") != 1
        log.info(f"Running: {running}")
        code = rep["job"].get("code")
        if True not in running.values():
            log.info(rep["job"].get("description", f"job completed with code {code}"))
            return code
        time.sleep(5)


def test_tech_sign_ins(evt_id):
    """Test alerting on tech sign ins"""
    log.info("Testing prior known sign-in")
    assert (
        run_cronicle_sync(
            evt_id,
            {
                "ARGS": "--now=2025-03-25T16:30:00",
                "CHAN_OVERRIDE": COVR,
            },
        )
        == 0
    )
    input(f"\nCheck {COVR} and confirm no messages sent; Enter to continue: ")

    log.info("Testing invalid sign-in")
    assert (
        run_cronicle_sync(
            evt_id,
            {
                "ARGS": "--now=3000-01-01T12:30:00",
                "CHAN_OVERRIDE": COVR,
            },
        )
        == 0
    )
    input(f"\nCheck {COVR} and confirm a message was sent; Enter to continue: ")


def _setup_test_event():
    # Start time is chosen to trigger the LOW_ATTENDANCE_7DAYS condition
    start = tznow() + datetime.timedelta(days=5)
    end = start + datetime.timedelta(hours=3)
    evt_id = neon_base.create_event(
        "Test event",
        "An event for integration testing use of Cronicle",
        start,
        end,
        dry_run=False,
        published=False,  # Doesn't show up in public listing
        registration=True,
    )
    log.info(f"Created dummy unpublished event #{evt_id}")
    try:
        status, content = airtable.append_classes_to_schedule(
            [
                {
                    "Instructor": "Cronicle",
                    "Email": "hello@protohaven.org",
                    "Start Time": start.isoformat(),
                    "Class": ["recyvKjNGHHCuHeFw"],  # wood 101
                    "Confirmed": tznow().isoformat(),
                    "Neon ID": evt_id,
                }
            ]
        )
        rec = content["records"][0]["id"]
        log.info(f"Created schedule record {rec}: {status} {content}")
    except Exception:
        log.error("Exception encountered; cleaning up prod data before raising")
        _cleanup_test_event(evt_id, rec)
        raise
    return evt_id, rec


def _cleanup_test_event(evt_id, rec):
    if rec:
        log.info(f"Cleaning up class schedule record {rec}")
        print(airtable_base.delete_record("class_automation", "schedule", rec))
    if evt_id:
        log.info(f"Cleaning up Neon event {evt_id}")
        print(neon_base.delete("api_key3", f"/events/{evt_id}"))


def test_send_class_emails(cronicle_evt_id):
    """Test sending email updates"""
    # Note: this does not test tech backfill nor instructor readiness emails
    # It could be done by moving the class start date around.
    evt_id, rec = _setup_test_event()
    try:
        assert (
            run_cronicle_sync(
                cronicle_evt_id,
                {
                    # Only act on the event we created; it's unpublished.
                    "ARGS": f"--filter={evt_id} --no-published_only --no-cache",
                    "CHAN_OVERRIDE": COVR,
                    "EMAIL_OVERRIDE": EOVR,
                },
            )
            == 0
        )
        print(f"\n- Notice should have been sent to {COVR}")
        print(f"- Email re: low attendence should have been sent to {EOVR}")
        input("Verify these two notifications; Enter to continue:")
    finally:
        _cleanup_test_event(evt_id, rec)


def test_simple(evt_id: str, params: dict):
    """Simple test of Cronicle job without any setup/teardown"""
    assert run_cronicle_sync(evt_id, params) == 0
    print("\n")
    if "CHAN_OVERRIDE" in params:
        print(f"-Notice sent to {params['CHAN_OVERRIDE']}")
    if "DM_OVERRIDE" in params:
        print(f"-Notice sent to {params['DM_OVERRIDE']}")
    if "EMAIL_OVERRIDE" in params:
        print(f"-Notice sent to {params['EMAIL_OVERRIDE']}")
    # In the future, may be able to fetch the job log and check
    # for specific substrings, e.g.
    # https://cronicle.api.protohaven.org/api/app/get_job_log?id=<job_id>
    input("Confirm message was sent; Enter to continue:")


if __name__ == "__main__":
    readonly_commands = [
        # Readonly commands
        ("sign_ins", test_tech_sign_ins, "elzn07uwhqg"),
        (
            "check_doors",
            test_simple,
            "em5wzj6552l",
            {"CHAN_OVERRIDE": COVR},
        ),
        (
            "donations_summary",
            test_simple,
            "em78dbzj04f",
            {"CHAN_OVERRIDE": COVR},
        ),
        (
            "check_cameras",
            test_simple,
            "em5d0rdob1l",
            {"CHAN_OVERRIDE": COVR},
        ),
        ("class_emails", test_send_class_emails, "elwnkuoqf8g"),
        ("instructor_apps", test_simple, "elwnqdz2o8j", {"CHAN_OVERRIDE": COVR}),
        (
            "private_instruction",
            test_simple,
            "elzadpyaqmj",
            {"CHAN_OVERRIDE": COVR, "EMAIL_OVERRIDE": EOVR},
        ),
        (
            "private_instruction_daily",
            test_simple,
            "elziy4cxkp4",
            {"CHAN_OVERRIDE": COVR},
        ),
        ("class_proposals", test_simple, "elx994dfv2o", {"CHAN_OVERRIDE": COVR}),
        ("shop_tech_apps", test_simple, "elw7tf3bg4s", {"CHAN_OVERRIDE": COVR}),
        # Note: this should really create some transaction violation problem for
        # reporting purposes
        ("square_txns", test_simple, "elw7tp2fs4x", {"CHAN_OVERRIDE": COVR}),
        # Note: we should ideally filter to specific memberships that we've
        # intentionally created as invalid.
        ("membership_val", test_simple, "elxbtcrmq3d", {"CHAN_OVERRIDE": COVR}),
        (
            "instructor_sched",
            test_simple,
            "em1zpa3989p",
            {
                "CHAN_OVERRIDE": COVR,
                "EMAIL_OVERRIDE": EOVR,
                "ARGS": (
                    "--start=2000-01-01 --end=2000-01-30 "
                    "--no-require_active --filter=test@test.com"
                ),
            },
        ),
        # Note: should change this to always produce a stale alert
        (
            "purchase_requests",
            test_simple,
            "em1zphtib9s",
            {
                "CHAN_OVERRIDE": COVR,
            },
        ),
        # Note: should change this to always produce a stale alert
        (
            "leads_maintenance",
            test_simple,
            "em1zpe87a9q",
            {
                "CHAN_OVERRIDE": COVR,
            },
        ),
        # Note: should change this to always produce a stale alert
        (
            "validate_docs",
            test_simple,
            "elzx3r1hlu5",
            {
                "CHAN_OVERRIDE": COVR,
            },
        ),
    ]
    asana_task_completing_commands = [
        # Note: need to submit a fake phone message here
        (
            "phone_msgs",
            test_simple,
            "elw7tkk5n4v",
            {
                "EMAIL_OVERRIDE": EOVR,
                "ARGS": "--no-apply",
            },
        ),
        # Note: need to submit a fake project request here
        (
            "project_requests",
            test_simple,
            "elth9zp5g01",
            {
                "CHAN_OVERRIDE": COVR,
                "ARGS": "--no-apply",
            },
        ),
    ]
    additive_commands = [
        # Note: need to affect a tool state in order to properly test
        (
            "sync_tools",
            test_simple,
            "elvv9mdlx2j",
            {
                "CHAN_OVERRIDE": COVR,
                "ARGS": "--no-apply",
            },
        ),
        # Note: need to create a test class to post and ensure all good.
        (
            "post_classes",
            test_simple,
            "elzk399t7ph",
            {
                "CHAN_OVERRIDE": COVR,
                "EMAIL_OVERRIDE": EOVR,
                "ARGS": "--no-apply",
            },
        ),
        # Note: should inject a task that's ready for maintenance
        (
            "maint_tasks",
            test_simple,
            "eltiobjj002",
            {
                "CHAN_OVERRIDE": COVR,
                "ARGS": "--no-apply",
            },
        ),
        # Note: should inject a storage violation
        (
            "policy_enforcement",
            test_simple,
            "elzd1jx39n8",
            {
                "CHAN_OVERRIDE": COVR,
                "EMAIL_OVERRIDE": EOVR,
                "ARGS": "--no-apply",
            },
        ),
        (
            "backup_wiki",
            test_simple,
            "em4u369ldgl",
            {
                "CHAN_OVERRIDE": COVR,
                "ARGS": '--no-apply --parent_id=""',
            },
        ),
        (
            "sync_booked_members",
            test_simple,
            "em5ahun5604",
            {
                "CHAN_OVERRIDE": COVR,
                "ARGS": "--no-apply",
            },
        ),
        (
            "restock_discounts",
            test_simple,
            "em6fgimj413",
            {
                "CHAN_OVERRIDE": COVR,
                "ARGS": "--no-apply",
            },
        ),
    ]
    destructive_commands = [
        # Need to modify a test user to properly exercise this command
        (
            "discord_nick",
            test_simple,
            "elzx3nvdvu4",
            {
                "CHAN_OVERRIDE": COVR,
                "DM_OVERRIDE": DOVR,
                "ARGS": "--no-apply --filter=pwacata --warn_not_associated",
            },
        ),
        # Need to modify a test discord user to exercise this
        (
            "discord_role",
            test_simple,
            "elzsp1fmpsk",
            {
                "CHAN_OVERRIDE": COVR,
                "DM_OVERRIDE": DOVR,
                "ARGS": "--no-apply_records --no-apply_discord --no-destructive --filter=pwacata",
            },
        ),
        # Need to test-initialize a member, see test_membership.py
        (
            "init_memberships",
            test_simple,
            "em1zpg3sc9r",
            {
                "CHAN_OVERRIDE": COVR,
                "EMAIL_OVERRIDE": EOVR,
                "ARGS": "--no-apply --filter=1245",
            },
        ),
    ]
    prober_commands = [
        ("probe_events", test_simple, "em3xcyglgdj", {}),
        ("probe_homepage", test_simple, "em403g0czew", {}),
    ]

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base_url",
        default="https://cron.protohaven.org/",
        help="Base URL for Cronicle commands",
    )
    parser.add_argument(
        "--api_key", required=True, help="API key for Cronicle commands"
    )
    parser.add_argument(
        "--command", default=None, help="command to run (leave empty to run all)"
    )
    parser.add_argument(
        "--after", default=None, help="run all commands after this one in sequence"
    )
    args = parser.parse_args()
    init_connector(Connector)

    base_url = args.base_url
    api_key = args.api_key

    print(f"Go to {base_url}/#Home and check the Countdown list under Upcoming Events.")
    print(
        "DO NOT PROCEED if you plan to test any events scheduled to execute within 10 minutes!"
    )
    assert input('Type "none upcoming" and press Enter to proceed: ') == "none upcoming"

    tests = (
        prober_commands
        + readonly_commands
        + asana_task_completing_commands
        + additive_commands
        + destructive_commands
    )
    events = cronicle_event_schedule()
    all_ids = {e["id"] for e in events["rows"]}
    tested_ids = {e[2] for e in tests}
    if len(all_ids - tested_ids):
        raise RuntimeError(f"Some IDs in Cronicle are not tested: {all_ids-tested_ids}")

    for i, tc in enumerate(tests):
        name, fn, eid = tc[:3]
        if args.command and args.command != name:
            continue
        if args.after:
            if name == args.after:
                args.after = None
            continue

        log.info(f"\n\nRun test {i+1}/{len(tests)}: {tc}")
        if len(tc) == 4:
            fn(eid, tc[3])
        else:
            fn(eid)
