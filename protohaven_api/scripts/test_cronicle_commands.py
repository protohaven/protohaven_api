"""Integration tests for Cronicle jobs/events"""
import logging
import time

import requests

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

base_url = None  # pylint: disable=invalid-name
api_key = None  # pylint: disable=invalid-name
TIMEOUT = 60 * 5


def run_cronicle_sync(event_id, params):
    """Starts a job on Cronicle"""
    log.info(f"{base_url} START {event_id} PARAMS {params}")
    rep = requests.post(
        f"{base_url}/api/app/run_event/v2",
        headers={"X-API-Key": api_key},
        timeout=TIMEOUT,
        json={"id": event_id, "retries": 0, "timeout": TIMEOUT, "params": params},
    ).json
    log.info(str(rep))
    running = {rid: False for rid in rep["ids"]}
    for rid in running.keys():
        log.info(f"{base_url}#JobDetails?id={rid}")
    while True:
        for rid in running.keys():
            rep = requests.get(
                f"{base_url}/api/app/get_job_status/v1?id={rid}",
                headers={"X-API-Key": api_key},
                timeout=TIMEOUT,
            )
            running[rid] = rep.json["job"]["complete"] != 1
        log.info(f"Running: {running}")
        if True not in running.values():
            log.info("Complete!")
            return
        time.sleep(5)


def test_tech_sign_ins(evt_id):
    """Test alerting on tech sign ins"""
    run_cronicle_sync(evt_id, {})


# def test_send_class_emails(evt_id):
#     pass
# def test_instructor_applications(evt_id):
#     pass
# def test_private_instruction(evt_id):
#     pass
# def test_private_instruction_daily(evt_id):
#     pass
# def test_class_proposals(evt_id):
#     pass
# def test_shop_tech_applications(evt_id):
#     pass
# def test_square_transactions(evt_id):
#     pass
# def test_validate_memberships(evt_id):
#     pass
# def test_gen_instructor_schedule_reminder(evt_id):
#     pass
# def test_purchase_request_alerts(evt_id):
#     pass
# def test_gen_tech_leads_maintenance_summary(evt_id):
#     pass
# def test_validate_docs(evt_id):
#     pass
# def test_phone_messages(evt_id):
#     pass
# def test_project_requests(evt_id):
#     pass
# def test_post_classes(evt_id):
#     pass
# def test_gen_maintenance_tasks(evt_id):
#     pass
# def test_sync_tools(evt_id):
#     pass
# def test_enforce_discord_nicknames(evt_id):
#     pass
# def test_update_role_intents(evt_id):
#     pass
# def test_init_new_membersihps(evt_id):
#     pass

if __name__ == "__main__":
    test_commands = [
        # Readonly commands
        ("sign_ins", test_tech_sign_ins, "elzn07uwhqg"),
        # ("class_emails", test_send_class_emails, 'elwnkuoqf8g'),
        # ("instructor_apps", test_instructor_applications, 'elwnqdz2o8j'),
        # ("private_instruction", test_private_instruction, 'elzadpyaqmj'),
        # ("private_instruction_daily", test_private_instruction_daily, 'elziy4cxkp4'),
        # ("class_proposals", test_class_proposals, 'elx994dfv2o'),
        # ("shop_tech_apps", test_shop_tech_applications, 'elw7tf3bg4s'),
        # ("square_txns", test_square_transactions, 'elw7tp2fs4x'),
        # ("membership_val", test_validate_memberships, 'elxbtcrmq3d'),
        # ("instructor_sched", test_gen_instructor_schedule_reminder, 'em1zpa3989p'),
        # ("purchase_requests", test_purchase_request_alerts, 'em1zphtib9s'),
        # ("leads_maintenance", test_gen_tech_leads_maintenance_summary, 'em1zpe87a9q'),
        # ("validate_docs", test_validate_docs, 'elzx3r1hlu5'),
        # Asana task completing commands
        # ("phone_msgs", test_phone_messages, 'elw7tkk5n4v'),
        # ("project_requests", test_project_requests, "elth9zp5g01"),
        # Additive commands
        # ("post_classes", test_post_classes_to_neon, 'elzk399t7ph'),
        # ("maint_tasks", test_gen_maintenance_tasks, 'eltiobjj002'),
        # ("sync_tools", test_sync_reservable_tools, 'elvv9mdlx2j'),
        # Destructive / mutation commands
        # ("discord_nick", test_enforce_discord_nicknames, 'elzx3nvdvu4'),
        # ("discord_role", test_update_role_intents, 'elzsp1fmpsk'),
        # ("init_memberships", test_init_new_membersihps, 'em1zpg3sc9r'),
    ]

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base_url",
        default="https://cronicle.api.protohaven.org/",
        help="Base URL for Cronicle commands",
    )
    parser.add_argument(
        "--api_key", required=True, help="API key for Cronicle commands"
    )
    parser.add_argument(
        "--command", default=None, help="command to run (leave empty to run all)"
    )
    args = parser.parse_args()
    base_url = args.base_url
    api_key = args.api_key

    print(f"Go to {base_url}/#Home and check the Countdown list under Upcoming Events.")
    print(
        "DO NOT PROCEED if you plan to test any events scheduled to execute within 10 minutes!"
    )
    assert input('Type "none upcoming" and press Enter to proceed') == "none upcoming"

    for name, fn, eid in test_commands:
        if args.command and args.command != name:
            continue
        fn(eid)
