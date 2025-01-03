"""Commands related to facility and equipment maintenance"""

import argparse
import logging
import random
import tempfile
import traceback
from pathlib import Path

from protohaven_api.automation.maintenance import manager
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import get_config, tznow
from protohaven_api.integrations import comms, drive, tasks, wiki, wyze
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
        arg(
            "--num",
            help="Max tasks to create",
            type=int,
            default=4,
        ),
    )
    def gen_maintenance_tasks(self, args, _):
        """Check recurring tasks list in Airtable, add new tasks to asana
        And notify techs about new and stale tasks that are tech_ready."""
        if not args.apply:
            log.warning("===========================================")
            log.warning("--no-apply is set; no tasks will be created")
            log.warning("===========================================")

        assert args.num > 0
        tt = manager.get_maintenance_needed_tasks()
        log.info(f"Found {len(tt)} needed maintenance tasks")
        tt.sort(key=lambda t: t["next_schedule"])
        errs = []
        scheduled = []

        for t in tt:
            log.info(
                f"Applying {t['id']} {t['name']} (section={t['section']}, tags={t['tags']})"
            )
            if args.apply:
                try:
                    t["gid"] = tasks.add_maintenance_task_if_not_exists(
                        t["name"],
                        t["detail"],
                        t["id"],
                        t["tags"],
                        section_gid=t["section"],
                    )
                    scheduled.append(t)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    traceback.print_exc()
                    errs.append(e)
            else:
                scheduled.append(t)

            if len(scheduled) >= args.num:
                break

        if len(errs) > 0:
            tasks_str = "\n".join([str(e) for e in errs])
            comms.send_discord_message(
                f"Errors when scheduling maintenance tasks:\n\n"
                f"{tasks_str}\nCheck Cronicle logs for details",
                "#tool-automation",
                blocking=False,
            )

        print_yaml(
            Msg.tmpl(
                "tech_daily_tasks",
                salutation=random.choice(SALUTATIONS),
                closing=random.choice(CLOSINGS),
                new_count=len(scheduled),
                new_tasks=scheduled,
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
                f"{not_in_config} configured in Wyze, "
                + "but not in protohaven_api config.yaml"
            )
        not_in_wyze = expected - cameras
        if len(not_in_wyze) > 0:
            warnings.append(
                f"{not_in_wyze} expected per protohaven_api "
                + "config.yaml, but not present in Wyze"
            )
        for c in camera_states:
            if not c.get("is_online"):
                warnings.append(
                    f"{c['name']} offline " + "(check power cable/network connection)"
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

    def _do_backup(  # pylint: disable=too-many-arguments
        self, fn, backup_path, upload_path, parent_id, apply
    ):
        file_sz = fn(backup_path)
        log.info(f"Fetched {backup_path}; pushing to drive as {upload_path}")
        if apply:
            file_id = drive.upload_file(
                backup_path,
                "application/x-gzip-compressed",
                upload_path,
                parent_id,
            )
            log.info(f"Uploaded, id {file_id}")
        else:
            file_id = "DRY_RUN"
            file_sz = 0
        return {"drive_id": file_id, "size_kb": file_sz // 1024, "name": upload_path}

    @command(
        arg(
            "--parent_id",
            help="destination folder ID",
            type=str,
            required=True,
        ),
        arg(
            "--apply",
            help="actually create the backup",
            action=argparse.BooleanOptionalAction,
            default=True,
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
                    apply=args.apply,
                )
            )
            pct[0] = 1.0
            stats.append(
                self._do_backup(
                    wiki.fetch_files_backup,
                    Path(d) / "files_backup.tar.gz",
                    f"files_backup_{now.isoformat()}.tar.gz",
                    args.parent_id,
                    apply=args.apply,
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
