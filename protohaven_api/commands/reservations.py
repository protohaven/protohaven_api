"""Commands related to reserving equipment and the Booked reservation system"""

import argparse
import logging
from functools import lru_cache

from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.integrations import airtable, booked, neon
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.reservation")


class Commands:
    """Commands for reserving equipment and configuring the Booked reservation system"""

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
        reservable = t["fields"].get("Current Status", "Unknown").split()[
            0
        ].lower() in ("green", "yellow")
        return booked.stage_tool_update(
            r,
            {
                "area": area,
                "tool_code": tool_code or "",
                "clearance_code": clearance_code,
            },
            reservable=reservable,
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
        arg(
            "--exclude_areas",
            help="CSV of areas to exclude from syncing",
            default=None,
        ),
    )
    def sync_reservable_tools(  # pylint: disable=too-many-branches, too-many-statements, too-many-locals
        self, args, pct
    ):
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
        pct.set_stages(4)
        if not args.apply:
            log.warning("==== --apply NOT SET, NO CHANGES WILL BE MADE ====")
        if args.filter is not None:
            args.filter = {a.strip() for a in args.filter.split(",")}
            log.warning(f"Filtering to tools by tool code: {args.filter}")
        if args.exclude_areas is not None:
            args.exclude_areas = {a.strip() for a in args.exclude_areas.split(",")}
            log.warning(f"Excluding areas: {args.exclude_areas}")
        else:
            args.exclude_areas = set()
        groups = {
            k.replace("&amp;", "&"): v
            for k, v in booked.get_resource_group_map().items()
        }
        pct[0] = 1
        in_airtable = set(self._area_colors().keys()) - args.exclude_areas
        in_booked = set(groups.keys()) - args.exclude_areas

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
        pct[1] = 1

        airtable_booked_ids = set()
        summary = []
        all_resources = {r["resourceId"]: r for r in booked.get_resources()}
        tools = list(airtable.get_tools())
        for i, t in enumerate(tools):
            pct[2] = i / len(tools)
            if not t["fields"].get("Reservable", False):
                continue
            r = all_resources.get(t["fields"].get("BookedResourceId"))
            if not r:
                summary.append(
                    f"Create placeholder resource for {t['fields'].get('Tool Name')}"
                )
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
        pct[3] = 0.5

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
                    )
                ]
            )
        else:
            print_yaml([])

    def _fetch_neon_sources(self):
        neon_members = []
        for member in neon.search_all_members(
            [
                "Company ID",
                "First Name",
                "Last Name",
                "Email 1",
                "Account Current Membership Status",
                neon.CustomField.BOOKED_USER_ID,
            ]
        ):
            if not member.email or not member.can_reserve_tools():
                continue
            neon_members.append(member)
        log.info(
            f"Fetched {len(neon_members)} neon members with email addresses that "
            "can reserve tools"
        )
        return neon_members

    def _fetch_booked_sources(self):
        booked_users = booked.get_all_users()
        booked_user_data = {user.id: user for user in booked_users}
        log.info(f"Fetched {len(booked_user_data)} booked users")
        return booked_user_data

    @command(
        arg(
            "--apply",
            help="If false, don't perform changes",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--exclude",
            help="CSV of email addresses of users to exclude from syncing",
            default=None,
        ),
        arg(
            "--include",
            help="CSV of email addresses of users to strictly include",
        ),
    )
    def sync_booked_members(
        self, args, pct
    ):  # pylint: disable=too-many-statements, too-many-locals, too-many-branches
        """Ensures that members are able to reserve tools, and non-members are not.

        Members are authed to Booked using their first name, last name, and email address.
        See https://www.bookedscheduler.com/help/oauth/oauth-configuration/
        We must make sure these fields match between Neon and Booked.
        """

        if args.exclude is not None:
            args.exclude = {a.strip().lower() for a in args.exclude.split(",")}
            log.warning(f"excluding users by email: {args.exclude}")
        else:
            args.exclude = set()
        if args.include is not None:
            args.include = {a.strip().lower() for a in args.include.split(",")}
            log.warning(f"including users by email: {args.include}")

        pct.set_stages(4)
        neon_members = self._fetch_neon_sources()
        pct[0] = 1
        booked_user_data = self._fetch_booked_sources()
        email_to_booked_user = {
            user.email.lower(): user for user in booked_user_data.values()
        }
        pct[1] = 1

        summary = []
        booked_member_ids = set()
        for i, member in enumerate(neon_members):
            pct[2] = i / len(neon_members)
            member_email_lower = member.email.lower()
            if member_email_lower in args.exclude:
                log.info(f"Skipping excluded {member.email}")
                continue
            if args.include and member_email_lower not in args.include:
                log.info(f"Skipping not explicitly included {member.email}")
                continue

            booked_id = member.booked_id
            if not booked_id:
                log.info(
                    f"Active member {member.full_name} ({member.email}) with no Booked User ID"
                )
                existing_booked_user = email_to_booked_user.get(member_email_lower)
                if existing_booked_user:
                    log.info(
                        f"Existing booked user with email {member.email}; associating that"
                    )
                    booked_id = existing_booked_user.id
                elif args.apply:
                    u = booked.create_user_as_member(
                        member.fname, member.lname, member.email
                    )
                    if u.get("errors"):
                        for e in u["errors"]:
                            log.error(e)
                        summary.append(
                            f"Error(s) setting up Booked user for {member.full_name}: "
                            f"{u.get('errors')}"
                        )
                        continue
                    booked_id = u["userId"]

                if booked_id and args.apply:
                    booked_member_ids.add(int(booked_id))
                    neon.set_booked_user_id(member.neon_id, booked_id)
                    summary.append(
                        f"Booked #{booked_id} associated with neon #{member.neon_id} "
                        f"{member.full_name}"
                    )
                    log.info(summary[-1])
            else:
                existing_booked_user = booked_user_data.get(booked_id)
                if not existing_booked_user:
                    raise RuntimeError(
                        f"Neon user {member.full_name} has invalid booked user ID {booked_id}"
                    )
                booked_member_ids.add(booked_id)
                # Check if the booked user data matches the neon member data
                booked_user_tuple = (
                    existing_booked_user.first_name,
                    existing_booked_user.last_name,
                    existing_booked_user.email,
                )
                member_tuple = (member.fname, member.lname, member.email.lower())
                if booked_user_tuple != member_tuple:
                    summary.append(
                        f"Update booked #{booked_id}: {booked_user_tuple} -> {member_tuple}"
                    )
                    log.info(summary[-1])
                    if args.apply:
                        data = booked.get_user(booked_id)
                        if not data or not data.get("id"):
                            raise RuntimeError(
                                f"Failed to get user data for {booked_id}: {data}"
                            )
                        data["firstName"] = member.fname
                        data["lastName"] = member.lname
                        data["emailAddress"] = member.email
                        rep = booked.update_user(booked_id, data)
                        log.info(f"Response {rep}")

        pct[3] = 0.5
        current_member_user_ids = {
            int(u.split("/")[-1]) for u in booked.get_members_group()["users"]
        }
        added_member_strings = [
            f"#{user.id} {user.full_name} ({user.email})"
            for user_id in booked_member_ids - current_member_user_ids
            if (user := booked_user_data.get(user_id))
        ]
        removed_member_strings = [
            f"#{user.id} {user.full_name} ({user.email})"
            for user_id in current_member_user_ids - booked_member_ids
            if (user := booked_user_data.get(user_id))
        ]
        if args.apply and booked_member_ids:
            log.info(str(booked.assign_members_group_users(booked_member_ids)))

        if len(added_member_strings) + len(removed_member_strings) > 0:
            summary.append(
                f"Assigning Members group to {len(booked_member_ids)} "
                + f"booked users (added {added_member_strings}, removed {removed_member_strings})"
            )
            log.info(summary[-1])

        if len(summary) > 0:
            print_yaml(
                [
                    Msg.tmpl(
                        "booked_member_sync_summary",
                        target="#tool-automation",
                        changes=summary,
                        n=len(summary),
                    )
                ]
            )
        else:
            print_yaml([])

    @command(
        arg(
            "--apply",
            help="If false, don't perform changes",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--days",
            help="Number of days in the future to check for orphaned reservations",
            type=int,
            default=90,
        ),
    )
    def cleanup_orphaned_class_reservations(self, args, pct):
        """Compare automation-created reservations with published classes and remove
        reservations that no longer have a matching, published class.

        This command:
        1. Fetches automation-created reservations (made by system@protohaven.org)
        2. Fetches published classes from Neon
        3. Matches reservations to classes by time and area
        4. Removes reservations without matching published classes
        """
        import datetime

        from protohaven_api.automation.classes import events as eauto
        from protohaven_api.config import tznow
        from protohaven_api.integrations.comms import Msg

        if not args.apply:
            log.warning("==== --apply NOT SET, NO CHANGES WILL BE MADE ====")

        pct.set_stages(4)

        # Step 1: Fetch published classes from Neon with Airtable data
        now = tznow()
        end_date = now + datetime.timedelta(days=args.days)

        log.info(f"Fetching published classes from {now} to {end_date}")
        published_events = []

        # Use fetch_upcoming_events which merges Neon and Airtable data
        try:
            for event in eauto.fetch_upcoming_events(
                back_days=0,  # Only future events
                published=True,  # Only published events
                merge_airtable=True,  # Merge with Airtable schedule data
                attendees=False,
                tickets=False,
            ):
                # Check if event ends within our time window
                if event.end_date and event.end_date <= end_date:
                    published_events.append(event)
        except Exception as e:
            log.warning(
                f"Error fetching events: {e}. Continuing with empty event list."
            )

        log.info(f"Found {len(published_events)} published events with Airtable data")
        pct[0] = 1

        # Step 2: Fetch automation-created reservations
        # Use the new helper function that gets all automation reservations
        interval = (now, end_date)
        automation_reservations = list(booked.get_automation_reservations(interval))

        log.info(
            f"Found {len(automation_reservations)} automation-created reservations"
        )
        pct[1] = 1

        # Step 3: Build map of class sessions by area and time
        class_time_map = {}
        for event in published_events:
            # Use the areas and sessions properties
            areas = event.areas
            sessions = event.sessions

            for area in areas:
                for session_start, session_end in sessions:
                    # Create time window key
                    key = (area, session_start, session_end)
                    class_time_map[key] = {
                        "neon_id": event.neon_id,
                        "name": event.name,
                    }

        log.info(f"Built time map with {len(class_time_map)} class sessions")
        pct[2] = 1

        # Step 4: Identify orphaned reservations
        orphaned_reservations = []
        summary = []

        # Get resource to area mapping
        res_to_area = booked.get_resource_area_map()

        # Check each automation reservation
        for reservation in automation_reservations:
            # Get reservation area
            reservation_area = None
            for area, resources in res_to_area.items():
                if reservation["resourceId"] in resources:
                    reservation_area = area
                    break

            if not reservation_area:
                log.warning(
                    f"Could not find area for reservation {reservation['referenceNumber']} with resource {reservation['resourceId']}"
                )
                continue

            # Check if there's a class at this time and area
            # Note: reservation times might be datetime strings or datetime objects
            reservation_start = reservation["startDate"]
            reservation_end = reservation["endDate"]

            # Convert to datetime if needed
            if isinstance(reservation_start, str):
                reservation_start = datetime.datetime.fromisoformat(
                    reservation_start.replace("Z", "+00:00")
                )
            if isinstance(reservation_end, str):
                reservation_end = datetime.datetime.fromisoformat(
                    reservation_end.replace("Z", "+00:00")
                )

            # Look for matching class session
            found_match = False
            for (area, class_start, class_end), class_info in class_time_map.items():
                if area == reservation_area:
                    # Check if reservation time overlaps with class time
                    # Using a tolerance of 5 minutes for time matching
                    time_tolerance = datetime.timedelta(minutes=5)
                    if (
                        abs((reservation_start - class_start).total_seconds())
                        <= time_tolerance.total_seconds()
                        and abs((reservation_end - class_end).total_seconds())
                        <= time_tolerance.total_seconds()
                    ):
                        found_match = True
                        break

            if not found_match:
                # This reservation doesn't have a matching published class
                orphaned_reservations.append(
                    {
                        "reference_number": reservation["referenceNumber"],
                        "resource_id": reservation["resourceId"],
                        "resource_name": reservation["resourceName"],
                        "area": reservation_area,
                        "start": reservation_start,
                        "end": reservation_end,
                        "title": reservation.get("title", ""),
                    }
                )

                summary.append(
                    f"Remove reservation #{reservation['referenceNumber']} for "
                    f"{reservation['resourceName']} in {reservation_area} "
                    f"({reservation_start} to {reservation_end}): "
                    f"{reservation.get('title', 'No title')}"
                )
                log.info(summary[-1])

        pct[3] = 1

        # Step 5: Remove orphaned reservations if apply is set
        if args.apply and orphaned_reservations:
            log.info(f"Removing {len(orphaned_reservations)} orphaned reservations")
            for orphan in orphaned_reservations:
                try:
                    result = booked.delete_reservation(orphan["reference_number"])
                    log.info(
                        f"Deleted reservation #{orphan['reference_number']}: {result}"
                    )
                except Exception as e:
                    log.error(
                        f"Failed to delete reservation #{orphan['reference_number']}: {e}"
                    )
                    summary.append(
                        f"Failed to delete reservation #{orphan['reference_number']}: {e}"
                    )

        # Output summary
        if len(summary) > 0:
            print_yaml(
                [
                    Msg.tmpl(
                        "orphaned_reservations_cleanup",
                        target="#tool-automation",
                        changes=summary,
                        n=len(orphaned_reservations),
                        apply=args.apply,
                    )
                ]
            )
        else:
            log.info("No orphaned reservations found")
            print_yaml([])
