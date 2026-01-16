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
        neon_members = {}
        for m in neon.search_all_members(
            [
                "Company ID",
                "First Name",
                "Last Name",
                "Email 1",
                "Account Current Membership Status",
                neon.CustomField.BOOKED_USER_ID,
            ]
        ):
            if not m.can_reserve_tools():
                continue
            neon_members[(m.fname, m.lname, m.email)] = (m.neon_id, m.booked_id)
        log.info(f"Fetched {len(neon_members)} neon members that can reserve tools")
        return neon_members

    def _fetch_booked_sources(self):
        booked_users = {
            int(u["id"]): (u["firstName"], u["lastName"], u["emailAddress"].lower())
            for u in booked.get_all_users()
        }
        log.info(f"Fetched {len(booked_users)} booked users")
        return booked_users

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
        booked_users = self._fetch_booked_sources()
        email_to_booked_user_id = {v[2].lower(): k for k, v in booked_users.items()}
        pct[1] = 1

        summary = []
        booked_members = set()
        for i, kv in enumerate(neon_members.items()):
            pct[2] = i / len(neon_members)
            k, v = kv
            if k[2].lower() in args.exclude:
                log.info(f"Skipping excluded {k[2]}")
                continue
            if args.include and k[2].lower() not in args.include:
                log.info(f"Skipping not explicitly included {k[2]}")
                continue

            aid, bid = v
            if not bid:
                log.info(f"Active member {k} with no Booked User ID")
                if email_to_booked_user_id.get(k[2].lower()):
                    log.info(
                        f"Existing booked user with email {k[2]}; associating that"
                    )
                    bid = email_to_booked_user_id[k[2].lower()]
                elif args.apply:
                    u = booked.create_user_as_member(k[0], k[1], k[2])
                    if u.get("errors"):
                        for e in u["errors"]:
                            log.error(e)
                        summary.append(
                            f"Error(s) setting up Booked user for {k}: {u.get('errors')}"
                        )
                        continue
                    bid = u["userId"]

                if bid and args.apply:
                    booked_members.add(int(bid))
                    neon.set_booked_user_id(aid, bid)
                    summary.append(f"Booked #{bid} associated with neon #{aid} {k}")
                    log.info(summary[-1])
            else:
                bk = booked_users.get(bid)
                if not bk:
                    raise RuntimeError(
                        f"Neon user {k} has invalid booked user ID {bid}"
                    )
                booked_members.add(bid)
                if bk != k:
                    summary.append(f"Update booked #{bid}: {bk} -> {k}")
                    log.info(summary[-1])
                    if args.apply:
                        data = booked.get_user(bid)
                        if not data or not data.get("id"):
                            raise RuntimeError(
                                f"Failed to get user data for {bid}: {data}"
                            )
                        data["firstName"] = k[0]
                        data["lastName"] = k[1]
                        data["emailAddress"] = k[2]
                        rep = booked.update_user(bid, data)
                        log.info(f"Response {rep}")

        pct[3] = 0.5
        cur_member_users = {
            int(u.split("/")[-1]) for u in booked.get_members_group()["users"]
        }
        added = [
            f"#{bid} {booked_users.get(bid)}"
            for bid in booked_members - cur_member_users
        ]
        removed = [
            f"#{bid} {booked_users.get(bid)}"
            for bid in cur_member_users - booked_members
        ]
        if len(added) + len(removed) > 0:
            summary.append(
                f"Assigning Members group to {len(booked_members)} "
                + f"booked users (added {added}, removed {removed})"
            )
            log.info(summary[-1])
            log.info(str(booked.assign_members_group_users(booked_members)))

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
