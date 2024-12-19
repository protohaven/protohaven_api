"""Commands related to facility and equipment maintenance"""
import argparse
import logging
import random
import tempfile
from pathlib import Path

from protohaven_api.automation.maintenance import manager
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import get_config, tznow
from protohaven_api.integrations import drive, wiki, wyze
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.maintenance")


SALUTATIONS = [
    "Greetings techs!",
    "Hey there, techs!",
    "Salutations, techs!",
    "Hello techs!",
    "Howdy techs!",
    "Yo techs!",
    "Good day, techs!",
    "Hiya techs!",
    "Ahoy techs!",
    "Hey ho, techs!",
    "Beep boop, hello fellow techs!",
    "What's up, techs!",
    "Greetings and salutations, techs!",
    "Hi techs, ready to make something?",
    "Hey there, tech wizards!",
    "Top of the morning, techs!",
]

CLOSINGS = [
    "Keep sparking those creative circuits!",
    "For adventure and maker glory!",
    "Stay wired!",
    "Onwards to innovation!",
    "May your creativity be boundless!",
    "Stay charged and keep on making!",
    "Let's make some sparks!",
    "May your projects shine brighter than LEDs!",
    "Let's keep the gears turning and the ideas flowing!",
    "Until our next digital rendezvous, stay charged up!",
    "Dream it, plan it, do it!",
    "Innovation knows no boundaries - keep pushing forward!",
    "Every project is a step closer to greatness - keep going!",
    "Always be innovating!",
    "Stay curious, stay inspired, and keep making a difference!",
    "Remember - every circuit starts with a single connection. Keep connecting!",
    "Your passion fuels progress — keep the fire burning!",
    "You're not just making things, you're making history — keep on crafting!",
    "From concept to creation, keep the momentum!",
    "Invent, iterate, and inspire — the maker's trifecta!",
]

MAX_STALE_TASKS = 3


class Commands:
    """Commands for managing maintenance tasks"""

    @command(
        arg(
            "--apply",
            help="actually create new Asana tasks",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
    )
    def gen_maintenance_tasks(self, args, _):
        """Check recurring tasks list in Airtable, add new tasks to asana
        And notify techs about new and stale tasks that are tech_ready."""
        tt = manager.run_daily_maintenance(args.apply)
        print_yaml(
            Msg.tmpl(
                "tech_daily_tasks",
                salutation=random.choice(SALUTATIONS),
                closing=random.choice(CLOSINGS),
                new_count=len(tt),
                new_tasks=tt,
                id="daily_maintenance",
                target="#techs-live",
            )
        )

    @command()
    def gen_tech_leads_maintenance_summary(self, _1, _2):
        """Report on status of equipment maintenance & stale tasks"""
        stale = manager.get_stale_tech_ready_tasks()
        if len(stale) > 0:
            log.info(f"Found {len(stale)} stale tasks")
            stale.sort(key=lambda k: k["days_ago"], reverse=True)
            print_yaml(
                Msg.tmpl(
                    "tech_leads_maintenance_status",
                    stale_count=len(stale),
                    stale_thresh=manager.DEFAULT_STALE_DAYS,
                    stale_tasks=stale[:MAX_STALE_TASKS],
                    id="daily_maintenance",
                    target="#tech-leads",
                )
            )
        else:
            print_yaml([])

    @command()
    def check_door_sensors(self, _1, _2):
        """Check the door sensors to make sure they're configured and the doors are closed"""
        wyze.init()
        expected = set(get_config("wyze/door_names"))
        door_states = list(wyze.get_door_states())
        doors = {d["name"] for d in door_states}
        warnings = []

        not_in_config = doors - expected
        if len(not_in_config) > 0:
            warnings.append(
                f"Door(s) {not_in_config} configured in Wyze, "
                + "but not in protohaven_api config.yaml"
            )

        not_in_wyze = expected - doors
        if len(not_in_wyze) > 0:
            warnings.append(
                f"Door(s) {not_in_wyze} expected per protohaven_api "
                + "config.yaml, but not present in Wyze"
            )
        for d in door_states:
            if not d.get("is_online"):
                warnings.append(
                    f"Door {d['name']} offline; check battery and/or "
                    + "[Wyze Sense Hub](https://www.wyze.com/products/wyze-hms-bundle)"
                )
            elif not d.get("open_close_state"):
                warnings.append(f"**IMPORTANT**: Door {d['name']} is open")
        if len(warnings) > 0:
            print_yaml(
                Msg.tmpl(
                    "door_sensor_warnings",
                    warnings=warnings,
                    target="#tech-leads",
                )
            )
        else:
            print_yaml([])

    @command()
    def check_cameras(self, _1, _2):
        """Check wyze cameras to make sure they're connected and working"""
        wyze.init()
        expected = set(get_config("wyze/camera_names"))
        camera_states = list(wyze.get_camera_states())
        cameras = {c["name"].strip() for c in camera_states}
        warnings = []
        not_in_config = cameras - expected
        if len(not_in_config) > 0:
            warnings.append(
                f"Camera(s) {not_in_config} configured in Wyze, "
                + "but not in protohaven_api config.yaml"
            )
        not_in_wyze = expected - cameras
        if len(not_in_wyze) > 0:
            warnings.append(
                f"Camera {not_in_wyze} expected per protohaven_api "
                + "config.yaml, but not present in Wyze"
            )
        for c in camera_states:
            if not c.get("is_online"):
                warnings.append(
                    f"camera {c['name']} offline "
                    + "(check power cable/network connection)"
                )
        if len(warnings) > 0:
            print_yaml(
                Msg.tmpl(
                    "camera_check_warnings",
                    warnings=warnings,
                    target="#tech-leads",
                )
            )
        else:
            print_yaml([])

    def _do_backup(self, fn, backup_path, upload_path, parent_id):
        file_sz = fn(backup_path)
        log.info(f"Fetched {backup_path}; pushing to drive as {upload_path}")
        file_id = drive.upload_file(
            backup_path,
            "application/x-gzip-compressed",
            upload_path,
            parent_id,
        )
        log.info(f"Uploaded, id {file_id}")
        return {"drive_id": file_id, "size_kb": file_sz // 1024, "name": upload_path}

    @command(
        arg(
            "--parent_id",
            help="destination folder ID",
            type=str,
            required=True,
        ),
    )
    def backup_wiki(self, args, pct):
        """Fetch and back up wiki data to google drive"""
        pct.set_stages(2)
        now = tznow()

        # Note: dest drive must be shared with protohaven-cli@protohaven-api.iam.gserviceaccount.com
        stats = []
        with tempfile.TemporaryDirectory() as d:
            stats.append(
                self._do_backup(
                    wiki.fetch_db_backup,
                    Path(d) / "db_backup.sql.gz",
                    f"db_backup_{now.isoformat()}.sql.gz",
                    args.parent_id,
                )
            )
            pct[0] = 1.0
            stats.append(
                self._do_backup(
                    wiki.fetch_files_backup,
                    Path(d) / "files_backup.tar.gz",
                    f"files_backup_{now.isoformat()}.tar.gz",
                    args.parent_id,
                )
            )
            pct[1] = 1.0

        print_yaml(
            Msg.tmpl(
                "wiki_backup_summary",
                parent_id=args.parent_id,
                stats=stats,
                target="#docs-automation",
            )
        )
        log.info("Done")
