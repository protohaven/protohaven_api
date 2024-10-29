"""Commands related to reserving equipment and the Booked reservation system"""

import argparse
import datetime
import logging

from dateutil import parser as dateparser

from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import (  # pylint: disable=import-error
    exec_details_footer,
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

    def _stage_booked_record_update(self, r, custom_attributes, **kwargs):
        changes = []
        r, changed_attrs = booked.stage_custom_attributes(r, **custom_attributes)
        if True in changed_attrs.values():
            changes.append(
                f"custom attributes ({changed_attrs} -> {custom_attributes})"
            )
            log.warning(
                f"Changed custom attributes: {changed_attrs} -> {custom_attributes}"
            )
        for k, v in kwargs.items():
            if str(r[k]) != str(v):
                log.warning(f"Changing {k} from {r[k]} to {v}")
                r[k] = v
                changes.append(f"{k} ({r[k]}->{v})")
        return r, changes

    @command(
        arg(
            "--apply",
            help="If false, don't perform changes",
            action=argparse.BooleanOptionalAction,
            default=False,
        )
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

        # Some areas we don't care about in the reservation system; these are excluded
        exclude_areas = {
            "Class Supplies",
            "Maintenance",
            "Staff Room",
            "Back Yard",
            "Fishbowl",
            "Maker Market",
            "Rack Storage",
            "Restroom 1",
            "Restroom 2",
            "Kitchen",
            "Gallery",
            "Custodial Room",
            "All",
        }

        area_colors = {}
        for a in airtable.get_areas():
            if not a["fields"].get("Name"):
                continue
            area_colors[a["fields"]["Name"]] = a["fields"].get("Color")

        groups = {
            k.replace("&amp;", "&"): v
            for k, v in booked.get_resource_group_map().items()
        }
        in_airtable = set(area_colors.keys()) - exclude_areas
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

        # print("Resource Group ID map:")
        # for k,v in groups.items():
        #    print(f"- {k} = {v}")
        airtable_booked_ids = set()
        summary = []
        for t in airtable.get_tools():
            if not t["fields"].get("Reservable", False):
                continue
            d = {
                "name": t["fields"].get("Tool Name"),
                "resourceId": t["fields"].get("BookedResourceId"),
                "reservable": t["fields"]
                .get("Current Status", "Unknown")
                .split()[0]
                .lower()
                in ("green", "yellow"),
                "area": t["fields"].get("Name (from Shop Area)", [None])[0],
                "clearance_code": t["fields"].get(
                    "Clearance Code (from Clearance Required)", [None]
                )[0]
                or "",
                "tool_code": t["fields"].get("Tool Code"),
            }
            if not d["name"] or not d["area"]:
                log.warning(f"Record {t['id']} missing name or area: {d}")

            if not d[
                "resourceId"
            ]:  # New tool! Create the record. We'll update it in a second step
                log.warning(f"Creating new resource {d['name']}")
                summary.append(f"Create new Booked resource {d['name']}")
                if not args.apply:
                    log.warning(f"Skipping creation of new resource {d['name']}")
                    continue
                rep = booked.create_resource(d["name"])
                log.debug(str(rep))
                log.debug("Updating airtable record")
                d["resourceId"] = rep["resourceId"]
                rep = airtable.set_booked_resource_id(t["id"], d["resourceId"])
                log.debug(str(rep))
            airtable_booked_ids.add(d["resourceId"])

            log.info(f"#{d['resourceId']} \"{d['name']}\"")
            r = booked.get_resource(d["resourceId"])
            r, changes = self._stage_booked_record_update(
                r,
                {
                    "area": d["area"],
                    "tool_code": d["tool_code"],
                    "clearance_code": d["clearance_code"],
                },
                name=f"{d['area']} - {d['name']}",
                statusId=(
                    booked.STATUS_AVAILABLE
                    if d["reservable"]
                    else booked.STATUS_UNAVAILABLE
                ),
                typeId=booked.TYPE_TOOL,
                color=area_colors.get(d.get("area")) or "",
                allowMultiday=d.get("area")
                == "3D Printing",  # 3D printers allow reservations across days
            )
            if changes:
                summary.append(f"Change {d['name']}: {', '.join(changes)}")
                if args.apply:
                    log.info(booked.update_resource(r))

        # Note 2024-04-15: groupIds don't seem to be editable via standard
        # update. We'd have to mock admin panel behavior
        # groupIds=[groups[a] for a in d.get("area", []) if a is not None],

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
