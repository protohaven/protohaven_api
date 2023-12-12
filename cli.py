# A set of command line tools, usually run by CRON
import argparse
import neon
import sheets
import airtable
import datetime
import comms
import tasks
import re
from collections import defaultdict
import requests
import sys
from dateutil import parser as dateparser

def send_hours_submission_reminders(dry_run = True):
    now = datetime.datetime.now()
    earliest = now - datetime.timedelta(days=14)
    classes = neon.fetch_events(
            after=earliest,
            before=now + datetime.timedelta(days=1)
    )
    # TODO binary search for date, or store submissions better in general
    subs = set([s['Class Name (Please type out full name of class)'] for s in sheets.get_instructor_submissions(900) if s['Timestamp'] > earliest])
    
    print(f"Loaded {len(subs)} submissions after {earliest}")

    to_remind = defaultdict(list)
    for c in classes:
        if c['name'] in subs:
            print("Class", c['name'], "already submitted, skipping")
            continue

        m = re.match(".*w\/ (\w+) (\w+)", c['name'])
        if m is None:
            print("Skipping unparseable event:", c['name'])
            continue

        # TODO lookup and cache
        inst = neon.search_member_by_name(m[1], m[2])
        if inst is None:
            print("Couldn't find Neon info for ", m[1], m[2])
            continue
        email = inst['Email 1']
        to_remind[email].append(c['name'])

    for email, names in to_remind.items():
        body = f"Greetings!"
        body += f"\n\nWe haven't yet seen your submission for the following course(s):\n"
        for n in names:
            body += "\n - " + n
        body += "\n\nPlease submit your hours and any clearances earned by visiting the following link ASAP: https://api.protohaven.org/instructor_hours"
        body += "\n\nThanks for being a great instructor!\nSincerely, the Protohaven Automation System"

        subject = "Please submit your hours!"
        if dry_run:
            print("\n\nDRY RUN - NOT SENDING:")
            print("To:", email)
            print("Subject:", subject)
            print(body)
        else:
            raise Exception("TEST THIS FIRST")
            comms.send_email(subject, body, [email])

def send_storage_violation_reminders():
    # TODO For any violation tagged with a user, send an email
    # Send a summary of violations without users to a discord channel / email location
    raise Exception("TODO implement")

def validate_member_clearances():
    # TODO match clearances in spreadsheet with clearances in Neon.
    # Remove this when clearance information is primarily stored in Neon.
    raise Exception("TODO implement")

def validate_tool_documentation():
    # Go through list of tools in airtable, ensure all of them have
    # links to a tool guide and a clearance doc that resolve successfully
    
    def probe(url, name, stats):
        url = url.strip()
        if url != "" and url != "https://protohaven.org/wiki/tools//":
            rep = requests.get(url)
            if rep.status_code == 200:
                stats['ok'] += 1
            else:
                stats['error'].append(f"{name} ({url})")
        else:
            stats['missing'].append(name)
    stats = {
            "tooldoc": dict(missing=[], error=[], ok=0),
            "clearance": dict(missing=[], error=[], ok=0),
            }
    tools = airtable.get_tools()
    sys.stdout.write(f"Checking links for {len(tools)} tools")
    sys.stdout.flush()
    for i, tool in enumerate(tools):
        if i != 0 and i % 5 == 0:
            sys.stdout.write(str(i))
        name = tool['fields']['Tool Name']

        clearance_url = tool['fields']['Clearance']['url']
        probe(clearance_url, name, stats['clearance'])

        tutorial_url = tool['fields']['Docs']['url']
        probe(tutorial_url, name, stats['tooldoc'])

        rep = requests.head(tutorial_url)
        tutorial_exists = rep.status_code == 200

        # print(f"{name}\n - Clearance url: {clearance_url}\n - Tutorial url: {tutorial_url}\n")
        sys.stdout.write(".")
        sys.stdout.flush()

    subject = "Tool documentation report, " + datetime.datetime.now().isoformat()
    body = "\nChecked {len(tools)} tools"
    def write_stats(stats, title):
        b = f"\n\n=== {title} ==="
        b += f"\n{stats['ok']} links resolved OK"
        b += f"\nMissing links for {len(stats['missing'])} tools"
        for m in stats['missing']:
            b += f"\n - {m}"
        b += f"\nFailed to resolve {len(stats['error'])} links for tools"
        for m in stats['error']:
            b += f"\n - {m}"
        return b
    body += write_stats(stats['tooldoc'], "Tool Tutorials")
    body += "\n"
    body += write_stats(stats['clearance'], "Clearance Docs")
    recipients = ["scott@protohaven.org"]
    print(f"Sending email to {recipients}:\n{subject}\n\n{body}")
    comms.send_email(subject, body, recipients)
    print("Email sent")

def cancel_low_attendance_classes():
    # TODO fetch classes from neon
    pass

completion_re = re.compile('Deadline for Project Completion:\n(.*?)\n', re.MULTILINE)
description_re = re.compile('Project Description:\n(.*?)Materials Budget', re.MULTILINE)
def project_request_alerts():
    for req in tasks.get_project_requests():
        if req['completed']:
            continue
        req['notes'] = req['notes'].replace('\\n', '\n')
        deadline = completion_re.search(req['notes'])
        if deadline is None:
            raise Exception("Failed to extract deadline from request by " + req['name'])
        deadline = dateparser.parse(deadline[1])
        if deadline < datetime.datetime.now():
            print(f"Skipping expired project request by {req['name']} (expired {deadline})")
            continue

        content = "**New Project Request:**\n"
        content += req['notes']
        send_help_wanted(content)
        tasks.complete(req['gid'])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                    prog='Protohaven CLI',
                    description='Command line utility for protohaven operations')
    parser.add_argument('command')

    args = parser.parse_args()
    if args.command == "reminder":
        send_hours_submission_reminders()
    elif args.command == "validate_docs":
        validate_tool_documentation()
    elif args.command == "project_requests":
        project_request_alerts()
