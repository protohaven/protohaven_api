""" A set of command line tools, possibly run by CRON"""

import argparse
import datetime
import json
import logging
import os
import re
import sys
from collections import defaultdict

import pytz
import yaml
from dateutil import parser as dateparser

from protohaven_api.class_automation import scheduler
from protohaven_api.class_automation.builder import (
    ClassEmailBuilder,
    gen_calendar_reminders,
)
from protohaven_api.config import get_config
from protohaven_api.integrations import airtable, comms, neon, sheets, tasks
from protohaven_api.integrations.airtable import log_email
from protohaven_api.integrations.comms import send_discord_message, send_email
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.maintenance import manager
from protohaven_api.policy_enforcement import enforcer
from protohaven_api.validation.docs import validate as validate_docs

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
log = logging.getLogger("cli")
server_mode = os.getenv("PH_SERVER_MODE", "dev").lower()
log.info(f"Mode is {server_mode}\n")
init_connector(dev=server_mode != "prod")

tz = pytz.timezone("EST")


def send_hours_submission_reminders(dry_run=True):
    """Sends reminders to instructors to submit their hours"""
    now = datetime.datetime.now()
    earliest = now - datetime.timedelta(days=14)
    classes = neon.fetch_events(after=earliest, before=now + datetime.timedelta(days=1))
    # Would be more efficient to binary search for date
    # or store submissions better in general
    subs = {
        s["Class Name (Please type out full name of class)"]
        for s in sheets.get_instructor_submissions(900)
        if s["Timestamp"] > earliest
    }

    log.info(f"Loaded {len(subs)} submissions after {earliest}")

    to_remind = defaultdict(list)
    for c in classes:
        if c["name"] in subs:
            log.info(f"Class {c['name']} already submitted, skipping")
            continue

        m = re.match(r".*w\/ (\w+) (\w+)", c["name"])
        if m is None:
            log.info(f"Skipping unparseable event: {c['name']}")
            continue

        # Could lookup and cache this, later
        inst = neon.search_member_by_name(m[1], m[2])
        if inst is None:
            log.info(f"Couldn't find Neon info for {m[1]} {m[2]}")
            continue
        email = inst["Email 1"]
        to_remind[email].append(c["name"])

    for email, names in to_remind.items():
        body = "Greetings!"
        body += "\n\nWe haven't yet seen your submission for the following course(s):\n"
        for n in names:
            body += "\n - " + n
        body += "\n\nPlease submit your hours and any clearances earned by visiting"
        body += " the following link ASAP: https://api.protohaven.org/instructor_hours"
        body += "\n\nThanks for being a great instructor!"
        body += "\nSincerely, the Protohaven Automation System"

        subject = "Please submit your hours!"
        if dry_run:
            log.info("\n\nDRY RUN - NOT SENDING:")
            log.info(f"To: {email}")
            log.info(f"Subject: {subject}")
            log.info(body)
        else:
            raise RuntimeError("TEST THIS FIRST")
            # comms.send_email(subject, body, [email])


completion_re = re.compile("Deadline for Project Completion:\n(.*?)\n", re.MULTILINE)
description_re = re.compile("Project Description:\n(.*?)Materials Budget", re.MULTILINE)


def purchase_request_alerts():
    """Send alerts when there's purchase requests that haven't been acted upon for some time"""
    content = "**Open Purchase Requests Report:**"
    sections = defaultdict(list)
    counts = defaultdict(int)
    now = datetime.datetime.now().astimezone(tz)
    thresholds = {
        "low_pri": 7,
        "high_pri": 2,
        "class_supply": 3,
        "on_hold": 30,
        "unknown": 0,
    }
    headers = {
        "low_pri": "Low Priority",
        "high_pri": "High Priority",
        "class_supply": "Class Supplies",
        "on_hold": "On Hold",
        "unknown": "Unknown/Unparsed Tasks",
    }

    def format_request(t):
        if (t["modified_at"] - t["created_at"]).days > 1:
            dt = (now - t["modified_at"]).days
            dstr = f"modified {dt}d ago"
        else:
            dt = (now - t["created_at"]).days
            dstr = f"created {dt}d ago"
        return (f"- {t['name']} ({dstr})", dt)

    for t in tasks.get_open_purchase_requests():
        counts[t["category"]] += 1
        thresh = now - datetime.timedelta(days=thresholds[t["category"]])
        if t["created_at"] < thresh and t["modified_at"] < thresh:
            sections[t["category"]].append(format_request(t))

    # Sort oldest to youngest, by section
    for k, v in sections.items():
        v.sort(key=lambda t: -t[1])
        sections[k] = [t[0] for t in v]

    section_added = False
    for k in ("high_pri", "class_supply", "low_pri", "on_hold", "unknown"):
        if len(sections[k]) > 0:
            section_added = True
            content += f"\n\n{headers[k]} ({counts[k]} total open; "
            content += f"showing only tasks older than {thresholds[k]} days):\n"
            content += "\n".join(sections[k])

    if not section_added:
        content += "\nAll caught up. Nice."

    log.info(content)
    comms.send_board_message(content)
    log.info("Done")


class ProtohavenCLI:
    """argparser-based CLI for protohaven operations"""

    def __init__(self):
        self.log = logging.getLogger("cli")
        helptext = "\n".join(
            [
                f"{a}: {getattr(self, a).__doc__}"
                for a in dir(self)
                if not a.startswith("__")
            ]
        )
        parser = argparse.ArgumentParser(
            description="Protohaven CLI",
            usage=f"{sys.argv[0]} <command> [<args>]\n\n{helptext}\n\n\n",
        )
        parser.add_argument("command", help="Subcommand to run")
        args = parser.parse_args(sys.argv[1:2])  # Limit to only initial command args
        if not hasattr(self, args.command):
            parser.print_help()
            sys.exit(1)
        getattr(self, args.command)(
            sys.argv[2:]
        )  # Ignore first two argvs - already parsed

    def gen_instructor_calendar_reminder(self, argv):
        """Reads the list of instructors from Airtable and generates
        reminder comms to all instructors, plus the #instructors discord,
        to update their calendars for availability"""
        parser = argparse.ArgumentParser(
            description=self.gen_instructor_calendar_reminder.__doc__
        )
        parser.add_argument(
            "--start",
            help="start date for calendar reminder window",
            type=str,
            required=True,
        )
        parser.add_argument(
            "--end",
            help="end date for calendar reminder window",
            type=str,
            required=True,
        )
        args = parser.parse_args(argv)
        start = dateparser.parse(args.start)
        end = dateparser.parse(args.end)
        print(
            yaml.dump(
                gen_calendar_reminders(start, end),
                default_flow_style=False,
                default_style="",
            )
        )

    def gen_class_emails(self, argv):
        """Reads schedule of classes from Neon and Airtable and outputs
        a list of emails to send to instructors, techs, and students.
        This does not actually send the emails; for that, see send_comms."""
        parser = argparse.ArgumentParser(description=self.gen_class_emails.__doc__)
        parser.add_argument(
            "--confirm",
            help="class IDs to auto-confirm when generating emails",
            type=int,
            nargs="+",
        )
        parser.add_argument(
            "--cancel",
            help="class IDs to auto-cancel when generating emails",
            type=int,
            nargs="+",
        )
        parser.add_argument(
            "--ignore",
            help="class IDs to ignore when generating emails",
            type=int,
            nargs="+",
        )
        parser.add_argument(
            "--filter",
            help="class IDs to restrict processing to when generating emails",
            type=int,
            nargs="+",
        )
        args = parser.parse_args(argv)
        builder = ClassEmailBuilder(logging.getLogger("cli.email_builder"))
        builder.ignore_ovr = args.ignore or []
        builder.cancel_ovr = args.cancel or []
        builder.confirm_ovr = args.confirm or []
        builder.filter_ovr = args.filter or []
        # Add the rest here as needed

        result = builder.build()
        print(yaml.dump(result, default_flow_style=False, default_style=""))
        self.log.info(f"Generated {len(result)} notification(s)")

    def send_comms(self, argv):
        """Reads a list of emails and sends them to their recipients"""
        parser = argparse.ArgumentParser(description=self.send_comms.__doc__)
        parser.add_argument(
            "--path",
            help="path to comms YAML file (typically generated by another command)",
            type=str,
        )
        parser.add_argument(
            "--confirm",
            help="skip interactive confirmation; use for true automation",
            action=argparse.BooleanOptionalAction,
            default=False,
        )
        parser.add_argument(
            "--dryrun",
            help="just print them, don't send them",
            action=argparse.BooleanOptionalAction,
            default=False,
        )
        args = parser.parse_args(argv)

        with open(args.path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f.read())
        self.log.info(f"Loaded {len(data)} notifications:")
        for e in data:
            self.log.info(f" - {e['target']}: {e['subject']}")

        confstr = f"send {len(data)} notifications"
        if not args.dryrun and not args.confirm:
            confirm = input(f'Please type "{confstr}" to continue: ')
            if confirm != confstr:
                self.log.error("Confirmation string does not match; exiting")
                sys.exit(1)

        for e in data:
            if e["target"].startswith("#"):
                content = f"{e['subject']}\n\n{e['body']}"
                if args.dryrun:
                    print("DRY RUN to discord", e["target"])
                    print(content)
                else:
                    send_discord_message(content, e["target"].split("#")[1])
            else:
                email_validate_pattern = r"\S+@\S+\.\S+"
                emails = re.findall(
                    email_validate_pattern,
                    e["target"].replace(";", " ").replace(",", " ").lower(),
                )
                emails = [
                    e.replace("(", "")
                    .replace(")", "")
                    .replace('"', "")
                    .replace("'", "")
                    for e in emails
                ]

                if args.dryrun:
                    print("DRY RUN to", ", ".join(emails))
                    print("Subject:", e["subject"])
                    print(e["body"])
                else:
                    send_email(e["subject"], e["body"], emails)
                    log_email(e["id"], ", ".join(emails), e["subject"], "Sent")
                    self.log.info(
                        f"Sent to {emails}: '{e['subject']}' (logged in Airtable)"
                    )
        self.log.info("Done")

    def validate_docs(self, argv):  # pylint: disable=too-many-statements
        """Go through list of tools in airtable, ensure all of them have
        links to a tool guide and a clearance doc that resolve successfully"""
        parser = argparse.ArgumentParser(description=self.validate_docs.__doc__)
        parser.parse_args(argv)
        result = validate_docs()
        print(yaml.dump([result], default_flow_style=False, default_style=""))

    def project_requests(self, argv):
        """Send alerts when new project requests fall into Asana"""
        parser = argparse.ArgumentParser(description=self.validate_docs.__doc__)
        parser.add_argument(
            "--notify",
            help="when true, send requests to Discord and complete their task in Asana",
            action=argparse.BooleanOptionalAction,
            default=False,
        )
        args = parser.parse_args(argv)
        if not args.notify:
            log.info(
                "\n***   --notify is not set, so projects will not be "
                + "checked off or posted to Discord   ***\n"
            )
        num = 0
        for req in tasks.get_project_requests():
            if req["completed"]:
                continue
            req["notes"] = req["notes"].replace("\\n", "\n")
            deadline = completion_re.search(req["notes"])
            if deadline is None:
                raise RuntimeError(
                    "Failed to extract deadline from request by " + req["name"]
                )
            deadline = dateparser.parse(deadline[1])
            if deadline < datetime.datetime.now():
                log.info(
                    f"Skipping expired project request by {req['name']} (expired {deadline})"
                )
                continue

            content = "**New Project Request:**\n"
            content += req["notes"]
            if args.notify:
                comms.send_help_wanted(content)
                tasks.complete(req["gid"])
                log.info("Sent to discord & marked complete:")
            num += 1
            log.info(content)
        log.info(f"Done - handled {num} project request(s)")

    def new_violation(self, argv):
        """Create a new Violation in Airtable"""
        parser = argparse.ArgumentParser(description=self.new_violation.__doc__)
        parser.add_argument(
            "--reporter",
            help="who's reporting the violation",
            type=str,
            required=True,
        )
        parser.add_argument(
            "--suspect",
            help="who's suspected of causing the violation",
            type=str,
            default=None,
        )
        parser.add_argument(
            "--sections",
            help="comma-separated list of section IDs relevant to violation. See help for list",
            type=str,
            required=True,
        )
        parser.add_argument(
            "--fee", help="fee per day while violation is open", type=float, default=0.0
        )
        parser.add_argument("--notes", help="additional context", type=str, default="")
        args = parser.parse_args(argv)
        result = airtable.open_violation(
            args.reporter,
            args.suspect,
            args.sections.split(","),
            None,
            datetime.datetime.now(),
            args.fee,
            args.notes,
        )
        print(result)

    def build_scheduler_env(self, argv):
        """Construct an environment for assigning classes at times to instructors"""
        parser = argparse.ArgumentParser(description=self.build_scheduler_env.__doc__)
        parser.add_argument(
            "--start",
            help="Start date (yyyy-mm-dd)",
            type=str,
            required=True,
        )
        parser.add_argument(
            "--end",
            help="End date (yyyy-mm-dd)",
            type=str,
            required=True,
        )
        parser.add_argument(
            "--filter",
            help="CSV of subset instructors to filter scheduling to",
            type=str,
            required=False,
        )
        args = parser.parse_args(argv)
        start = dateparser.parse(args.start).astimezone(tz)
        end = dateparser.parse(args.end).astimezone(tz)
        inst = {a.strip() for a in args.filter.split(",")} if args.filter else None
        env = scheduler.generate_env(start, end, inst)
        print(yaml.dump(env, default_flow_style=False, default_style=""))

    def run_scheduler(self, argv):
        """Run the class scheduler on a provided env"""
        parser = argparse.ArgumentParser(description=self.run_scheduler.__doc__)
        parser.add_argument(
            "--path",
            help="path to env file",
            type=str,
            required=True,
        )
        args = parser.parse_args(argv)
        with open(args.path, "r", encoding="utf-8") as f:
            env = yaml.safe_load(f.read())
        instructor_classes, final_score = scheduler.solve_with_env(env)
        self.log.info(f"Final score: {final_score}")
        print(yaml.dump(instructor_classes, default_flow_style=False, default_style=""))

    def append_schedule(self, argv):
        """Adds a schedule (created with `run_scheduler`) to Airtable for
        instructor confirmation."""
        parser = argparse.ArgumentParser(description=self.append_schedule.__doc__)
        parser.add_argument(
            "--path",
            help="path to schedule file",
            type=str,
            required=True,
        )
        args = parser.parse_args(argv)
        with open(args.path, "r", encoding="utf-8") as f:
            sched = yaml.safe_load(f.read())
        notifications = scheduler.push_schedule(sched)
        print(yaml.dump(notifications, default_flow_style=False, default_style=""))

    def close_violation(self, argv):
        """Close out a violation so consequences cease"""
        parser = argparse.ArgumentParser(description=self.new_violation.__doc__)
        parser.add_argument(
            "--id",
            help="instance number for the violation",
            type=int,
            required=True,
        )
        parser.add_argument(
            "--closer",
            help="who's closing the violation",
            type=str,
            required=True,
        )
        parser.add_argument(
            "--suspect",
            help="suspect (if known)",
            type=str,
        )
        parser.add_argument(
            "--notes",
            help="any additionald details",
            type=str,
        )
        args = parser.parse_args(argv)
        result = airtable.close_violation(
            args.id, args.closer, datetime.datetime.now(), args.suspect, args.notes
        )
        print(result.status_code, result.content)

    def enforce_policies(self, argv):  # pylint: disable=too-many-locals
        """Follows suspension & violation logic for any ongoing violations.
        For any violation tagged with a user, generate comms.
        For any action needed to suspend users, generate comms.
        Also generate a summary of changes for sending to Discord."""
        parser = argparse.ArgumentParser(description=self.enforce_policies.__doc__)
        parser.add_argument(
            "--apply",
            help=(
                "Apply fees and suspension actions in Airtable. "
                "If false, they will only be printed"
            ),
            action=argparse.BooleanOptionalAction,
            default=False,
        )
        args = parser.parse_args(argv)

        violations = airtable.get_policy_violations()
        old_fees = [
            (f["fields"]["Violation"][0], f["fields"]["Amount"], f["fields"]["Created"])
            for f in airtable.get_policy_fees()
            if not f["fields"].get("Paid")
        ]
        new_fees = enforcer.gen_fees(violations)
        if len(new_fees) > 0:
            log.info("Generated fees:")
            for f in new_fees:
                log.info(f" - {f[2]} {f[0]} ${f[1]}")
            if args.apply:
                rep = airtable.create_fees(new_fees)
                log.debug(f"{rep.status_code}: {rep.content}")
                log.info(f"Applied {len(new_fees)} fee(s) into Airtable")
            else:
                log.warning("--apply not set; no fee(s) will be added")

        new_sus = enforcer.gen_suspensions()
        if len(new_sus) > 0:
            log.info("Generated suspensions:")
            for s in new_sus:
                log.info(f" - {s}")
            if args.apply:
                for neon_id, duration, violation_ids in new_sus:
                    start = datetime.datetime.now().astimezone(tz)
                    end = start + datetime.timedelta(duration)
                    rep = airtable.create_suspension(neon_id, violation_ids, start, end)
                    log.debug(f"{rep.status_code}: {rep.content}")
                log.info(f"Applied {len(new_sus)} suspension(s) into Airtable")
            else:
                log.warning("--apply not set; no suspension(s) will be added")

        # Update accrual totals so they're visible at protohaven.org/violations
        enforcer.update_accruals()

        result = enforcer.gen_comms(violations, old_fees, new_fees, new_sus)
        print(yaml.dump(result, default_flow_style=False, default_style=""))
        self.log.info(f"Generated {len(result)} notification(s)")

    def gen_maintenance_tasks(self, argv):
        """Check recurring tasks list in Airtable, add new tasks to asana
        And notify techs about new and stale tasks that are tech_ready."""
        parser = argparse.ArgumentParser(description=self.gen_maintenance_tasks.__doc__)
        parser.add_argument(
            "--dryrun",
            help="don't actually create new Asana tasks",
            action=argparse.BooleanOptionalAction,
            default=False,
        )
        args = parser.parse_args(argv)
        report = manager.run_daily_maintenance(args.dryrun)
        print(yaml.dump([report], default_flow_style=False, default_style=""))

    def validate_member_clearances(self, argv):
        """Match clearances in spreadsheet with clearances in Neon.
        Remove this when clearance information is primarily stored in Neon."""
        raise NotImplementedError("TODO implement")

    def cancel_classes(self, argv):
        """cancel passed classes by unpublishing and disabling registration"""
        parser = argparse.ArgumentParser(description=self.cancel_classes.__doc__)
        parser.add_argument(
            "--id",
            help="class IDs to cancel",
            type=str,
            nargs="+",
        )
        args = parser.parse_args(argv)
        for i in args.id:
            i = i.strip()
            log.info(f"Cancelling #{i}")
            neon.set_event_scheduled_state(i, scheduled=False)
        log.info("Done")

    def mock_data(self, argv):
        """Fetch mock data from airtable, neon etc.
        Write this to a file for running without touching production data"""
        parser = argparse.ArgumentParser(description=self.validate_docs.__doc__)
        parser.parse_args(argv)

        sys.stderr.write("Fetching events from neon...\n")
        events = neon.fetch_events()
        # Could also fetch attendees here if needed
        sys.stderr.write("Fetching clearance codes from neon...\n")
        clearance_codes = neon.fetch_clearance_codes()

        sys.stderr.write("Fetching accounts from neon...\n")
        accounts = []
        for acct_id in [1797, 1727, 1438, 1355]:
            accounts.append(neon.fetch_account(acct_id))

        sys.stderr.write("Fetching airtable data...\n")
        cfg = get_config()
        tables = defaultdict(dict)
        for k, v in cfg["airtable"].items():
            for k2 in v.keys():
                if k2 in ("base_id", "token"):
                    continue
                sys.stderr.write(f"{k} {k2}...\n")
                tables[k][k2] = airtable.get_all_records(k, k2)

        sys.stderr.write("Done. Results:\n")
        log.info(
            json.dumps(
                {
                    "neon": {
                        "events": events,
                        "accounts": accounts,
                        "clearance_codes": clearance_codes,
                    },
                    "airtable": tables,
                }
            )
        )


ProtohavenCLI()
