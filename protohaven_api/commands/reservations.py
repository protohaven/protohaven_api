"""Commands related to reserving equipment and the Booked reservation system"""
import argparse
import datetime
import functools
import logging
from collections import defaultdict

from dateutil import parser as dateparser

from protohaven_api.config import tz  # pylint: disable=import-error
from protohaven_api.integrations import airtable, booked  # pylint: disable=import-error

log = logging.getLogger("cli.reservation")


def command(*parser_args):
    """Returns a configured decorator that provides help info based on the function comment
    and parses all args given to the function"""

    def decorate(func):
        """Sets up help doc and parses all args"""

        @functools.wraps(func)
        def wrapper(*args):
            parser = argparse.ArgumentParser(description=func.__doc__)
            for cmd, pkwarg in parser_args:
                print(cmd, pkwarg)
                parser.add_argument(cmd, **pkwarg)
            parsed_args = parser.parse_args(args[1])  # argv
            return func(args[0], parsed_args)

        return wrapper

    return decorate


class Commands:
    """Commands for reserving equipment and configuring the Booked reservation system"""

    def _resolve_equipment_from_class(self, args_cls):
        results = defaultdict(
            lambda: {"name": "", "areas": None, "resources": [], "intervals": []}
        )
        # Resolve areas from class ID. We track the area name and not
        # record ID since we're operating on a synced copy of the areas when
        # we go to look up tools and equipment
        args_cls = [int(c) for c in args_cls.split(",")]
        for cls in airtable.get_class_automation_schedule():
            cid = cls["fields"]["ID"]
            if cid not in args_cls:
                continue
            results[cid]["areas"] = set(cls["fields"]["Name (from Area) (from Class)"])
            results[cid]["name"] = cls["fields"]["Name (from Class)"]
            start = dateparser.parse(cls["fields"]["Start Time"]).astimezone(tz)
            for d in range(cls["fields"]["Days (from Class)"][0]):
                offs = start + datetime.timedelta(days=7 * d)
                results[cid]["intervals"].append(
                    [
                        offs,
                        offs
                        + datetime.timedelta(
                            hours=cls["fields"]["Hours (from Class)"][0]
                        ),
                    ]
                )
        return results

    @command(
        (
            "--cls",
            {
                "help": "Scheduled class IDs to reserve equipment for (comma separated)",
                "type": str,
            },
        ),
        (
            "--apply",
            {
                "help": (
                    "Apply changes into Booked scheduler."
                    "If false, it will only be printed"
                ),
                "action": argparse.BooleanOptionalAction,
                "default": False,
            },
        ),
    )
    def reserve_equipment_for_class(self, args):
        """Resolves class info to a list of equipment that should be reserved,
        then reserves it by calling out to Booked"""
        results = self._resolve_equipment_from_class(args.cls)
        log.info(f"Resolved {len(results)} classes to areas")

        # Convert areas to booked IDs using tool table
        for row in airtable.get_all_records("tools_and_equipment", "tools"):
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

        for cid in results:
            log.info(f"Class {results[cid]['name']} (#{cid}):")
            for name, resource_id in results[cid]["resources"]:
                for start, end in results[cid]["intervals"]:
                    log.info(
                        f"  Reserving {name} (Booked ID {resource_id}) from {start} to {end}"
                    )
                    if args.apply:
                        log.info(
                            str(
                                booked.reserve_resource(
                                    resource_id, start, end, title=results[cid]["name"]
                                )
                            )
                        )

        log.info("Done")

    def _stage_booked_record_update(self, r, custom_attributes, **kwargs):
        r, changed_attrs = booked.stage_custom_attributes(r, **custom_attributes)
        if True in changed_attrs.values():
            log.warning(
                f"Changed custom attributes: {changed_attrs} -> {custom_attributes}"
            )
        changed = False
        for k, v in kwargs.items():
            if str(r[k]) != str(v):
                log.warning(f"Changing {k} from {r[k]} to {v}")
                r[k] = v
                changed = True
        return r, True in changed_attrs.values() or changed

    @command(
        (
            "--apply",
            {
                "help": "If false, don't perform changes",
                "action": argparse.BooleanOptionalAction,
                "default": False,
            },
        )
    )
    def sync_reservable_tools(self, args):  # pylint: disable=too-many-locals
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
                if not args.apply:
                    log.warning(f"Skipping creation of new resource {d['name']}")
                    continue
                log.warning(f"Creating new resource {d['name']}")
                rep = booked.create_resource(d["name"])
                log.debug(str(rep))
                log.debug("Updating airtable record")
                d["resourceId"] = rep["resourceId"]
                rep = airtable.set_booked_resource_id(t["id"], d["resourceId"])
                log.debug(str(rep))
            airtable_booked_ids.add(d["resourceId"])

            log.info(f"#{d['resourceId']} \"{d['name']}\"")
            r = booked.get_resource(d["resourceId"])
            r, changed = self._stage_booked_record_update(
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
            if args.apply:
                if changed:
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