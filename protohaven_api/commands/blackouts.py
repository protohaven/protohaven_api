"""Commands related to tech shift management and blackouts"""

import argparse
import datetime
import logging

from protohaven_api.automation.techs import techs as forecast
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tznow
from protohaven_api.integrations import booked
from protohaven_api.integrations.airtable import Interval

log = logging.getLogger("cli.blackouts")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for managing tech shifts and related blackouts"""

    @command(
        arg(
            "--apply",
            help="Actually create blackouts (dry run if false)",
            action=argparse.BooleanOptionalAction,
            default=False,
        ),
        arg(
            "--days-ahead",
            help="Number of days to check ahead for tech shifts",
            type=int,
            default=14,
        ),
        arg(
            "--start-date",
            help="Start date for checking tech shifts (YYYY-MM-DD format, defaults to today)",
            type=str,
            default=None,
        ),
    )
    def sync_booked_blackouts(
        self, args, _
    ):  # pylint: disable=too-many-statements,too-many-branches,too-many-locals,line-too-long
        """Sync Booked blackouts with tech shift forecast.

        For each day in the forecast period:
        - If a shift (AM or PM) has 0 techs scheduled, create blackouts for that shift
        - If both AM and PM shifts have 0 techs (or --block-full-day is true),
          create blackout for entire day
        - Remove existing blackouts when techs are now staffed for previously unstaffed shifts
        """
        # Parse start date
        if args.start_date:
            try:
                start_date = datetime.datetime.strptime(
                    args.start_date, "%Y-%m-%d"
                ).date()
                start_date = datetime.datetime.combine(start_date, datetime.time.min)
            except ValueError:
                log.error(
                    f"Invalid start date format: {args.start_date}. Use YYYY-MM-DD"
                )
                return
        else:
            start_date = tznow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Get tech shift forecast
        log.info(
            f"Getting tech shift forecast for {args.days_ahead} days "
            f"starting from {start_date.date()}"
        )
        forecast_data = forecast.generate(
            start_date, args.days_ahead, include_pii=False
        )
        calendar_view = forecast_data["calendar_view"]

        # Get all resources/tools from Booked
        log.info("Fetching all resources from Booked...")
        all_resources = booked.get_resources()
        resource_ids = [r["resourceId"] for r in all_resources]
        log.info(f"Found {len(resource_ids)} resources/tools in Booked")

        # Get existing blackouts to track what needs to be created/removed
        existing_blackouts = booked.get_blackouts(
            start_date=start_date,
            end_date=start_date + datetime.timedelta(days=args.days_ahead),
        )
        existing_blackout_map = {}  # (start, end) -> blackout_id
        blackouts_to_remove = []

        for blackout in existing_blackouts.get("blackouts", []):
            blackout_id = blackout.get("id") or blackout.get("blackoutId")
            if blackout_id:
                existing_blackout_map[
                    (blackout["startDateTime"], blackout["endDateTime"])
                ] = blackout_id

        # Track blackouts that should exist based on current forecast
        required_blackouts = set()
        blackouts_to_create = []
        for day in calendar_view:
            d = datetime.datetime.strptime(day["date"], "%Y-%m-%d")
            am_techs = len(day["AM"]["people"])
            pm_techs = len(day["PM"]["people"])
            log.info(
                f"{d}: AM shift has {am_techs} techs, PM shift has {pm_techs} techs"
            )

            if am_techs != 0 and pm_techs != 0:
                continue

            # Define shift times
            am_shift: Interval = [
                d.replace(hour=10, minute=0, second=0),
                d.replace(hour=16, minute=0, second=0),
            ]
            pm_shift: Interval = [
                d.replace(hour=16, minute=0, second=0),
                d.replace(hour=22, minute=0, second=0),
            ]
            start = am_shift[0] if am_techs == 0 else pm_shift[0]
            end = am_shift[1] if pm_techs != 0 else pm_shift[1]
            required_blackouts.add((start, end))
            if (start, end) not in existing_blackout_map:
                blackouts_to_create.append(
                    {
                        "date": d,
                        "reason": "No techs scheduled for AM shift",
                        "start": start,
                        "end": end,
                        "resource_ids": resource_ids,
                    }
                )
                log.info(f"  Will add blackout ({start.time()} to {end.time()})")

        # Identify blackouts to remove (exist but shouldn't based on current forecast)
        for (start, end), blackout_id in existing_blackout_map.items():
            if (start, end) not in required_blackouts:
                blackouts_to_remove.append(
                    {"id": blackout_id, "start": start, "end": end}
                )
                log.info(
                    f"  Will remove blackout (ID: {blackout_id}): {start.time()} to {end.time()}"
                )

        if not args.apply:
            log.warning("--no-apply, so no action taken.")
        else:
            # Create new blackouts
            if blackouts_to_create:
                log.info(f"\nCreating {len(blackouts_to_create)} blackout(s)...")
                for blackout in blackouts_to_create:
                    try:
                        result = booked.create_blackout(
                            start_date=blackout["start"],
                            end_date=blackout["end"],
                            resource_ids=blackout["resource_ids"],
                            title=f"Tech Shift Blackout - {blackout['date']}",
                            description=f"Automated blackout: {blackout['reason']}",
                        )
                        log.info(
                            f"  Created blackout: {blackout['date']} "
                            f"(ID: {result.get('blackoutId', 'N/A')})"
                        )
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        log.error(
                            f"  Failed to create blackout for {blackout['date']} {e}"
                        )

            # Remove unnecessary blackouts
            if blackouts_to_remove:
                log.info(f"\nRemoving {len(blackouts_to_remove)} blackout(s)...")
                for blackout in blackouts_to_remove:
                    try:
                        result = booked.delete_blackout(blackout["id"])
                        log.info(
                            f"  Removed blackout (ID: {blackout['id']}): "
                            f"{blackout['start'].time()} to {blackout['end'].time()}"
                        )
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        log.error(
                            f"  Failed to remove blackout (ID: {blackout['id']}): {e}"
                        )

        print_yaml([])
