""" A set of command line tools, possibly run by CRON"""
import argparse
import datetime
import json
import re
import sys
from collections import defaultdict

import requests
from dateutil import parser as dateparser

from protohaven_api.config import get_config
from protohaven_api.integrations import airtable, comms, neon, sheets, tasks


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

    print(f"Loaded {len(subs)} submissions after {earliest}")

    to_remind = defaultdict(list)
    for c in classes:
        if c["name"] in subs:
            print("Class", c["name"], "already submitted, skipping")
            continue

        m = re.match(r".*w\/ (\w+) (\w+)", c["name"])
        if m is None:
            print("Skipping unparseable event:", c["name"])
            continue

        # Could lookup and cache this, later
        inst = neon.search_member_by_name(m[1], m[2])
        if inst is None:
            print("Couldn't find Neon info for ", m[1], m[2])
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
            print("\n\nDRY RUN - NOT SENDING:")
            print("To:", email)
            print("Subject:", subject)
            print(body)
        else:
            raise RuntimeError("TEST THIS FIRST")
            # comms.send_email(subject, body, [email])


def send_storage_violation_reminders():
    """For any violation tagged with a user, send an email.
    Summary of violations without users to a discord channel / email location"""
    raise NotImplementedError("TODO implement")


def validate_member_clearances():
    """Match clearances in spreadsheet with clearances in Neon.
    Remove this when clearance information is primarily stored in Neon."""
    raise NotImplementedError("TODO implement")


def cancel_low_attendance_classes():
    """fetch classes from neon and cancel the ones with low
    attendance near enough to the deadline"""
    raise NotImplementedError("TODO")


completion_re = re.compile("Deadline for Project Completion:\n(.*?)\n", re.MULTILINE)
description_re = re.compile("Project Description:\n(.*?)Materials Budget", re.MULTILINE)


def purchase_request_alerts():
    """Send alerts when there's purchase requests that haven't been acted upon for some time"""
    content = "**Open Purchase Requests Report:**"
    sections = defaultdict(list)
    counts = defaultdict(int)
    now = datetime.datetime.now().astimezone()
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

    print(content)
    comms.send_board_message(content)
    print("Done")


class ProtohavenCLI:
    """argparser-based CLI for protohaven operations"""

    def __init__(self):
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

    def validate_docs(self, argv):  # pylint: disable=too-many-statements
        """Go through list of tools in airtable, ensure all of them have
        links to a tool guide and a clearance doc that resolve successfully"""
        parser = argparse.ArgumentParser(description=self.validate_docs.__doc__)
        parser.add_argument(
            "--email",
            help="send email to address. if empty, no email is sent",
            type=str,
            default="",
        )
        args = parser.parse_args(argv)
        if args.email != "":
            print(f"A report will be sent to {args.email}")
        else:
            print("Use --email to send the report to an email address")

        def probe(url, name, stats):
            url = url.strip()
            if url not in ("", "https://protohaven.org/wiki/tools//"):
                rep = requests.get(url, timeout=5.0)
                if rep.status_code == 200:
                    stats["ok"] += 1
                else:
                    stats["error"].append(f"{name} ({url})")
            else:
                stats["missing"].append(name)

        stats = {
            "tooldoc": {"missing": [], "error": [], "ok": 0},
            "clearance": {"missing": [], "error": [], "ok": 0},
        }
        tools = airtable.get_tools()
        sys.stdout.write(
            f"Checking links for {len(tools)} tools\n"
            + "Tools that do not require a clearance will be skipped.\n"
        )
        sys.stdout.flush()
        for i, tool in enumerate(tools):
            # recZz04FDZ9zr1PVh is "None" clearance
            if (
                tool["fields"]["Clearance Required"] is None
                or "recZz04FDZ9zr1PVh" in tool["fields"]["Clearance Required"]
            ):
                sys.stdout.write(".")
                sys.stdout.flush()
                continue
            if i != 0 and i % 5 == 0:
                sys.stdout.write(str(i))
            name = tool["fields"]["Tool Name"]

            clearance_url = tool["fields"]["Clearance"]["url"]
            probe(clearance_url, name, stats["clearance"])

            tutorial_url = tool["fields"]["Docs"]["url"]
            probe(tutorial_url, name, stats["tooldoc"])

            # rep = requests.head(tutorial_url, timeout=5.0)
            # tutorial_exists = rep.status_code == 200

            # print(f"{name}\n - Clearance url: {clearance_url}\n - Tutorial url: {tutorial_url}\n")
            sys.stdout.write("+")
            sys.stdout.flush()

        subject = "Tool documentation report, " + datetime.datetime.now().isoformat()
        body = f"\nChecked {len(tools)} tools"

        def write_stats(stats, title):
            b = f"\n\n=== {title} ==="
            b += f"\n{stats['ok']} links resolved OK"
            b += f"\nMissing links for {len(stats['missing'])} tools"
            for m in stats["missing"]:
                b += f"\n - {m}"
            b += f"\nFailed to resolve {len(stats['error'])} links for tools"
            for m in stats["error"]:
                b += f"\n - {m}"
            return b

        body += write_stats(stats["tooldoc"], "Tool Tutorials")
        body += "\n"
        body += write_stats(stats["clearance"], "Clearance Docs")
        if args.email != "":
            print(f"Sending email to {args.email}:\n{subject}\n\n{body}")
            comms.send_email(subject, body, [args.email])
            print("Email sent")
        else:
            print(subject)
            print(body)

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
            print(
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
                print(
                    f"Skipping expired project request by {req['name']} (expired {deadline})"
                )
                continue

            content = "**New Project Request:**\n"
            content += req["notes"]
            if args.notify:
                comms.send_help_wanted(content)
                tasks.complete(req["gid"])
                print("Sent to discord & marked complete:")
            num += 1
            print(content)
        print(f"Done - handled {num} project request(s)")

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
        print(
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


if __name__ == "__main__":
    ProtohavenCLI()
