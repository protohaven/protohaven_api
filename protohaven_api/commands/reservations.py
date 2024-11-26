"""Commands related to reserving equipment and the Booked reservation system"""

import argparse
import datetime
import logging
from functools import lru_cache

from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import (  # pylint: disable=import-error
    exec_details_footer,
    get_config,
    tz,
)
from protohaven_api.integrations import airtable, booked  # pylint: disable=import-error
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.reservation")


def reservation_dict_from_record(event):
    """Like reservation_dict(), but from an airtable record"""
    return reservation_dict(
        event["fields"]["Name (from Area) (from Class)"],
        event["fields"]["Name (from Class)"],
        event["fields"]["Start Time"],
        event["fields"]["Days (from Class)"][0],
        event["fields"]["Hours (from Class)"][0],
    )


def reservation_dict(areas, name, start, days, hours):
    """Convert params into a 'reservation dict' used to reserve resources at particular intervals"""
    start = dateparser.parse(start).astimezone(tz)
    intervals = []
    for d in range(days):
        offs = start + datetime.timedelta(days=7 * d)
        intervals.append(
            [
                offs,
                offs + datetime.timedelta(hours=hours),
            ]
        )
    return {"areas": set(areas), "name": name, "intervals": intervals, "resources": []}


class Commands:
    """Commands for reserving equipment and configuring the Booked reservation system"""

    @command(
        arg(
            "--cls",
            help="Template class ID to reserve equipment for",
            type=str,
        ),
        arg(
            "--start",
            help=("Start period of reservation"),
            type=str,
        ),
        arg(
            "--apply",
            help=(
                "Apply changes into Booked scheduler."
                "If false, it will only be printed"
            ),
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def reserve_equipment_from_template(self, args):
        """Resolves template info to a list of equipment that should be reserved,
        then reserves it"""
        cls = [
            t
            for t in airtable.get_all_class_templates()
            if str(t["fields"]["ID"]) == args.cls
        ][0]
        results = {}
        results[cls["fields"]["ID"]] = reservation_dict(
            cls["fields"]["Name (from Area)"],
            cls["fields"]["Name"],
            args.start,
            cls["fields"]["Days"],
            cls["fields"]["Hours"],
        )
        self._reserve_equipment_for_class_internal(results, args.apply)
        log.info("Done")

    @command(
        arg(
            "--cls",
            help="Scheduled (Airtable) class IDs to reserve equipment for (comma separated)",
            type=str,
        ),
        arg(
            "--apply",
            help=(
                "Apply changes into Booked scheduler."
                "If false, it will only be printed"
            ),
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
    )
    def reserve_equipment_for_class(self, args):
        """Resolves class info to a list of equipment that should be reserved,
        then reserves it by calling out to Booked"""
        # Resolve areas from class ID. We track the area name and not
        # record ID since we're operating on a synced copy of the areas when
        # we go to look up tools and equipment
        args_cls = [int(c) for c in args.cls.split(",")]
        results = {}
        for cls in airtable.get_class_automation_schedule():
            cid = cls["fields"]["ID"]
            if cid not in args_cls:
                continue
            results[cid] = reservation_dict(
                cls["fields"]["Name (from Area) (from Class)"],
                cls["fields"]["Name (from Class)"],
                cls["fields"]["Start Time"],
                cls["fields"]["Days (from Class)"][0],
                cls["fields"]["Hours (from Class)"][0],
            )
        log.info(f"Resolved {len(results)} class(es) to areas")
        self._reserve_equipment_for_class_internal(results, args.apply)
        log.info("Done")

    def _reserve_equipment_for_class_internal(self, results, apply):
        """Internal version of the same method, for use by post_classes_to_neon
        command in commands/classes.py"""
        # Convert areas to booked IDs using tool table
        for row in airtable.get_all_records("tools_and_equipment", "tools"):
            cid = None
            for cid in results:
                for a in row["fields"]["Name (from Shop Area)"]:
                    if a in results[cid]["areas"] and row["fields"].get(
                        "BookedResourceId"
                    ):
                        results[cid]["resources"].append(
                            (
                                row["fields"]["Tool Name"],
                                row["fields"]["BookedResourceId"],
                            )
                        )
                        break

        for cid, rr in results.items():
            log.info(
                f"Class {results[cid]['name']} (#{cid}) has {len(rr['resources'])} resources:"
            )
            for name, resource_id in rr["resources"]:
                for start, end in rr["intervals"]:
                    log.info(
                        f"  Reserving {name} (Booked ID {resource_id}) from {start} to {end}"
                    )
                    if apply:
                        log.info(
                            str(
                                booked.reserve_resource(
                                    resource_id, start, end, title=rr["name"]
                                )
                            )
                        )

    @lru_cache(maxsize=1)
    def _area_colors(self):
        ac = {}
        for a in airtable.get_areas():
            if not a["fields"].get("Name"):
                continue
            ac[a["fields"]["Name"]] = a["fields"].get("Color")
        return ac

    def _sync_reservable_tool(self, r, t):
        name = t["fields"].get("Tool Name")
        area = t["fields"].get("Name (from Shop Area)", [None])[0]
        if not area:
            raise RuntimeError(
                f"Airtable tool record {t['id']} missing name and/or area: {name} {area}"
            )

        resource_id = t["fields"].get("BookedResourceId")
        clearance_code = (
            t["fields"].get("Clearance Code (from Clearance Required)", [None])[0] or ""
        )
        tool_code = t["fields"].get("Tool Code")

        log.info(f'{tool_code} #{resource_id} "{name}"')
        r = booked.get_resource(resource_id)
        return booked.stage_tool_update(
            r,
            {
                "area": area,
                "tool_code": tool_code,
                "clearance_code": clearance_code,
            },
            reservable=True,
            name=f"{area} - {name}",
            color=self._area_colors().get(area) or "",
            # 3D printers allow reservations across days
            allowMultiday=(area == "3D Printing"),
        )

    def _sync_booked_permissions(
        self, airtable_booked_ids, all_resources, summary, apply
    ):
        perms = set(booked.get_members_group_tool_permissions())
        perms_delta = airtable_booked_ids - perms
        if len(perms_delta) > 0:
            log.info(
                "The following tool IDs aren't part of the Members group in Booked:"
            )
            for missing in [
                f"#{v['resourceId']} {v['name']}"
                for r, v in all_resources.items()
                if r in perms_delta
            ]:
                log.info(missing)
                summary.append(f"Add to Members group: {missing}")
            if apply:
                log.info("Updating Members group tool permissions...")
                # Note that `airtable_booked_ids` is populated such that all entries
                # are known to exist in Booked.
                log.info(
                    str(booked.set_members_group_tool_permissions(airtable_booked_ids))
                )

    @command(
        arg(
            "--apply",
            help="If false, don't perform changes",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--filter",
            help="CSV of Airtable tool codes to constrain sync to",
            default=None,
        ),
    )
    def sync_reservable_tools(
        self, args
    ):  # pylint: disable=too-many-locals, too-many-branches
        """Sync metadata of tools in Airtable with their entries in Booked. Create new
        resources in Booked if none exist, and back-propagate Booked IDs.
        After the sync, resources that exist in Booked and not in Airtable will
        raise an exception, but not acted upon.

        Booked "Resource Groups" are also assessed during the sync; if they do not
        exactly match the list of areas of all tools, an exception is thrown and
        no changes are made.
        2024-04-12: There is currently no programmatic way to create a resource
        group - it can only be done via the web interface.

        """
        if not args.apply:
            log.warning("==== --apply NOT SET, NO CHANGES WILL BE MADE ====")
        if args.filter is not None:
            args.filter = {a.strip() for a in args.filter.split(",")}
            log.warning(f"Filtering to tools by tool code: {args.filter}")

        exclude_areas = set(get_config("booked/exclude_areas"))
        log.info(f"Will exclude syncing areas: {exclude_areas}")
        groups = {
            k.replace("&amp;", "&"): v
            for k, v in booked.get_resource_group_map().items()
        }
        in_airtable = set(self._area_colors().keys()) - exclude_areas
        in_booked = set(groups.keys()) - exclude_areas

        log.info(
            f"Resolved {len(in_airtable)} airtable areas and {len(in_booked)} booked "
            "resource groups, minus excluded areas"
        )
        if in_airtable != in_booked:
            missing_from_booked = in_airtable - in_booked
            extra_in_booked = in_booked - in_airtable
            raise RuntimeError(
                f"Mismatch in Airtable Areas vs Booked Resource Groups:"
                f"\n- Present in Airtable but not Booked: {missing_from_booked}"
                f"\n- Additional in Booked not in Airtable or default filter: {extra_in_booked}"
                "\n\nTo remedy, add missing groups at "
                "https://reserve.protohaven.org/Web/admin/resources/#/groups"
            )

        airtable_booked_ids = set()
        summary = []
        all_resources = {r["resourceId"]: r for r in booked.get_resources()}
        for t in airtable.get_tools():
            if not t["fields"].get("Reservable", False):
                continue
            r = all_resources.get(t["fields"].get("BookedResourceId"))
            if not r:
                summary.append(f"Create placeholder resource for {t['fields']['Name']}")
                log.info(summary[-1])
                if args.apply:
                    r = booked.create_resource("placeholder")
                    airtable.set_booked_resource_id(t["id"], r["resourceId"])

            if not r:  # Note: args.apply == False or insert failure results in r = None
                continue

            airtable_booked_ids.add(int(r["resourceId"]))
            if (
                args.filter is not None
                and t["fields"].get("Tool Code").strip().upper() not in args.filter
            ):
                continue

            r, changes = self._sync_reservable_tool(r, t)
            if changes:
                summary.append(f"Change {r['name']}: {', '.join(changes)}")
                if args.apply:
                    log.info(booked.update_resource(r))

        self._sync_booked_permissions(
            airtable_booked_ids, all_resources, summary, args.apply
        )

        extra_booked_resources = {
            k: v
            for k, v in booked.get_resource_id_to_name_map().items()
            if k not in airtable_booked_ids
        }
        if len(extra_booked_resources) > 0:
            raise RuntimeError(
                f"These resources exist in Booked, but not in Airtable: {extra_booked_resources}"
            )
        log.info("Done - all resources in Booked exist in Airtable")

        if len(summary) > 0:
            print_yaml(
                [
                    Msg.tmpl(
                        "tool_sync_summary",
                        target="#tool-automation",
                        changes=summary,
                        n=len(summary),
                        footer=exec_details_footer(),
                    )
                ]
            )
        print_yaml([])
