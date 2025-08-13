"""Commands related to facility and equipment maintenance"""

import argparse
import logging
import random
import tempfile
import traceback
from pathlib import Path

from protohaven_api.automation.maintenance import manager
from protohaven_api.automation.techs import techs as forecast
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tznow
from protohaven_api.integrations import comms, drive, neon, tasks, wiki, wyze
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.maintenance")


SALUTATIONS = [
    "Tools ready, techs!",
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
    "Make on, techs!",
    "Laser focus, techs!",
    "Hello makers!",
    "Build it, techs!",
    "Workshop crew!",
    "Tinker time!",
]


CLOSINGS = [
    "Keep those tools humming and creativity buzzing!",
    "For maker magic and shop shenanigans!",
    "Stay safe and keep making!",
    "Onwards to the next awesome build!",
    "May your cuts be straight and your ideas wild!",
    "Stay powered up and keep those projects rolling!",
    "Let's make some sawdust and sparks!",
    "May your builds be tighter than your tolerances!",
    "Keep the shop messy and the ideas flowing!",
    "Until next time - keep those safety glasses on!",
    "Measure twice, cut once, innovate always!",
    "Every project is a chance to learn something new - keep at it!",
    "Make it, break it, fix it, repeat!",
    "Stay sharp (literally and figuratively)!",
    "Remember - every masterpiece starts with a first cut. Keep building!",
    "Your skills are your superpower - keep leveling up!",
    "You're not just building projects, you're building skills - keep at it!",
    "From sketch to sawdust, make it happen!",
    "Tinker, tweak, and triumph - the maker's way!",
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
                f"Applying {t['id']} {t['name']} (section={t['section']}, level={t['level']})"
            )
            if args.apply:
                try:
                    t["gid"] = tasks.add_maintenance_task_if_not_exists(
                        t["name"],
                        t["detail"],
                        t["id"],
                        t["level"],
                        section=t["section"],
                    )
                    scheduled.append(t)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    traceback.print_exc()
                    errs.append(e)
            else:
                t["gid"] = "NO_APPLY"  # Appease the templater
                scheduled.append(t)

            if len(scheduled) >= args.num:
                break

        tasks_str = "\n".join([str(e) for e in errs]).strip()
        if tasks_str:
            comms.send_discord_message(
                f"Errors when scheduling maintenance tasks:\n\n"
                f"{tasks_str}\nCheck Cronicle logs for details",
                "#tool-automation",
                blocking=False,
            )

        techs_on_duty = forecast.generate(tznow(), 1, include_pii=True).get(
            "calendar_view", [None]
        )[0]
        am_tech_discord = []
        pm_tech_discord = []
        if techs_on_duty:
            try:
                name_to_discord_dict = {
                    m.name: f"@{m.discord_user}"
                    for m in neon.search_members_with_discord_association(
                        [
                            neon.CustomField.DISCORD_USER,
                            "First Name",
                            "Last Name",
                            "Preferred Name",
                            neon.CustomField.PRONOUNS,
                        ]
                    )
                }
                log.info(
                    f"Loaded mapping of {len(name_to_discord_dict)} associated discord usernames"
                )
                am_tech_discord = [
                    name_to_discord_dict.get(t.name, t.name)
                    for t in techs_on_duty["AM"]["people"]
                ]
                log.info(f"AM techs: {am_tech_discord}")
                pm_tech_discord = [
                    name_to_discord_dict.get(t.name, t.name)
                    for t in techs_on_duty["PM"]["people"]
                ]
                log.info(f"PM techs: {pm_tech_discord}")
            except Exception as e:  # pylint: disable=broad-exception-caught
                comms.send_discord_message(
                    "Error looking up Discord users for mentioning in `gen_maintenance_tasks`:\n"
                    + traceback.print_exc()
                    + "\nCheck Cronicle logs for details",
                    "#tech-automation",
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
                am_tech_discord=am_tech_discord,
                pm_tech_discord=pm_tech_discord,
            )
        )

    @command(
        arg(
            "names",
            help="names to match against configuration in Wyze App",
            type=str,
            nargs="+",
        ),
    )
    def check_door_sensors(self, args, _):
        """Check the door sensors to make sure they're configured and the doors are closed"""
        expected = {n.strip() for n in args.names}
        door_states = list(wyze.get_door_states())
        doors = {d["name"] for d in door_states}
        warnings = []
        not_in_config = doors - expected
        if len(not_in_config) > 0:
            warnings.append(
                f"Door(s) {not_in_config} configured in Wyze, but not in config"
            )

        not_in_wyze = expected - doors
        if len(not_in_wyze) > 0:
            warnings.append(
                f"Door(s) {not_in_wyze} expected per config"
                + ", but not present in Wyze"
            )
        for d in door_states:
            if not d.get("is_online"):
                warnings.append(
                    f"Door {d['name']} offline; check battery and/or "
                    + "[Wyze Sense Hub](https://www.wyze.com/products/wyze-hms-bundle)"
                )
            elif d.get("open_close_state"):
                warnings.append(f"**IMPORTANT**: Door {d['name']} is open")
        if len(warnings) > 0:
            log.info(f"Found {warnings} warning event(s)")
            print_yaml(
                Msg.tmpl(
                    "door_sensor_warnings",
                    warnings=warnings,
                    target="#tech-automation",
                )
            )
        else:
            log.info("Nothing to report - we're all clear.")
            print_yaml([])

    @command(
        arg(
            "names",
            help="repeated list of names to match against configuration in Wyze App",
            type=str,
            nargs="+",
        ),
    )
    def check_cameras(self, args, _):
        """Check wyze cameras to make sure they're connected and working"""
        expected = {n.strip() for n in args.names}
        camera_states = list(wyze.get_camera_states())
        cameras = {c["name"].strip() for c in camera_states}
        warnings = []
        not_in_config = cameras - expected
        if len(not_in_config) > 0:
            warnings.append(f"{not_in_config} configured in Wyze, but not in config")
        not_in_wyze = expected - cameras
        if len(not_in_wyze) > 0:
            warnings.append(
                f"{not_in_wyze} expected per config, but not present in Wyze"
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
                    target="#tech-automation",
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
