"""Commands related to tech shift management and blackouts"""

import argparse
import datetime
import logging
from typing import Optional

from protohaven_api.automation.techs import techs as forecast
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tznow
from protohaven_api.integrations import booked

log = logging.getLogger("cli.tech_shifts")


class Commands:
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
        arg(
            "--block-full-day",
            help="Block reservations for entire day when no AM nor PM shift (default: true)",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
    )
    def sync_booked_blackouts(self, args, _):
        """Sync Booked blackouts with tech shift forecast.
        
        For each day in the forecast period:
        - If a shift (AM or PM) has 0 techs scheduled, create blackouts for that shift
        - If both AM and PM shifts have 0 techs (or --block-full-day is true), create blackout for entire day
        - Remove existing blackouts when techs are now staffed for previously unstaffed shifts
        """
        # Parse start date
        if args.start_date:
            try:
                start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
                start_date = datetime.datetime.combine(start_date, datetime.time.min)
            except ValueError:
                log.error(f"Invalid start date format: {args.start_date}. Use YYYY-MM-DD")
                return
        else:
            start_date = tznow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get tech shift forecast
        log.info(f"Getting tech shift forecast for {args.days_ahead} days starting from {start_date.date()}")
        forecast_data = forecast.generate(start_date, args.days_ahead, include_pii=False)
        calendar_view = forecast_data["calendar_view"]
        
        # Get all resources/tools from Booked
        log.info("Fetching all resources from Booked...")
        all_resources = booked.get_resources()
        resource_ids = [r["resourceId"] for r in all_resources]
        log.info(f"Found {len(resource_ids)} resources/tools in Booked")
        
        # Get existing blackouts to track what needs to be created/removed
        existing_blackouts = booked.get_blackouts(
            start_date=start_date,
            end_date=start_date + datetime.timedelta(days=args.days_ahead)
        )
        existing_blackout_map = {}  # (start, end) -> blackout_id
        blackouts_to_remove = []
        
        for blackout in existing_blackouts.get("blackouts", []):
            start = datetime.datetime.fromisoformat(blackout["startDateTime"].replace("Z", "+00:00"))
            end = datetime.datetime.fromisoformat(blackout["endDateTime"].replace("Z", "+00:00"))
            # Convert to naive datetime for comparison (command uses naive datetimes)
            if start.tzinfo:
                start = start.replace(tzinfo=None)
            if end.tzinfo:
                end = end.replace(tzinfo=None)
            
            blackout_id = blackout.get("id") or blackout.get("blackoutId")
            if blackout_id:
                existing_blackout_map[(start, end)] = blackout_id
        
        # Track blackouts that should exist based on current forecast
        required_blackouts = set()
        blackouts_to_create = []
        days_checked = 0
        
        for day in calendar_view:
            date_str = day["date"]
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            
            am_techs = len(day["AM"]["people"])
            pm_techs = len(day["PM"]["people"])
            
            log.info(f"{date_str}: AM shift has {am_techs} techs, PM shift has {pm_techs} techs")
            
            # Skip holidays (shop is closed anyway)
            if day["is_holiday"]:
                log.info(f"  Skipping holiday: {date_str}")
                continue
            
            days_checked += 1
            
            # Define shift times
            am_start = date_obj.replace(hour=10, minute=0, second=0)   # 10:00 AM
            am_end = date_obj.replace(hour=16, minute=0, second=0)     # 4:00 PM
            pm_start = date_obj.replace(hour=16, minute=0, second=0)   # 4:00 PM
            pm_end = date_obj.replace(hour=22, minute=0, second=0)     # 10:00 PM
            
            # Check if we should block entire day
            block_entire_day = args.block_full_day and (am_techs == 0 and pm_techs == 0)
            
            if block_entire_day:
                # Block entire day (10 AM to 10 PM)
                start_time = am_start
                end_time = pm_end
                
                required_blackouts.add((start_time, end_time))
                
                if (start_time, end_time) not in existing_blackout_map:
                    blackouts_to_create.append({
                        "date": date_str,
                        "type": "full_day",
                        "reason": "No techs scheduled for AM or PM shift",
                        "start": start_time,
                        "end": end_time,
                        "resource_ids": resource_ids
                    })
                    log.info(f"  Will create blackout for entire day: {start_time.time()} to {end_time.time()}")
                else:
                    blackout_id = existing_blackout_map[(start_time, end_time)]
                    log.info(f"  Blackout already exists for entire day (ID: {blackout_id})")
            
            else:
                # Check individual shifts
                if am_techs == 0:
                    required_blackouts.add((am_start, am_end))
                    
                    if (am_start, am_end) not in existing_blackout_map:
                        blackouts_to_create.append({
                            "date": date_str,
                            "type": "am_shift",
                            "reason": "No techs scheduled for AM shift",
                            "start": am_start,
                            "end": am_end,
                            "resource_ids": resource_ids
                        })
                        log.info(f"  Will create blackout for AM shift: {am_start.time()} to {am_end.time()}")
                    else:
                        blackout_id = existing_blackout_map[(am_start, am_end)]
                        log.info(f"  Blackout already exists for AM shift (ID: {blackout_id})")
                
                if pm_techs == 0:
                    required_blackouts.add((pm_start, pm_end))
                    
                    if (pm_start, pm_end) not in existing_blackout_map:
                        blackouts_to_create.append({
                            "date": date_str,
                            "type": "pm_shift",
                            "reason": "No techs scheduled for PM shift",
                            "start": pm_start,
                            "end": pm_end,
                            "resource_ids": resource_ids
                        })
                        log.info(f"  Will create blackout for PM shift: {pm_start.time()} to {pm_end.time()}")
                    else:
                        blackout_id = existing_blackout_map[(pm_start, pm_end)]
                        log.info(f"  Blackout already exists for PM shift (ID: {blackout_id})")
        
        # Identify blackouts to remove (exist but shouldn't based on current forecast)
        for (start, end), blackout_id in existing_blackout_map.items():
            if (start, end) not in required_blackouts:
                blackouts_to_remove.append({
                    "id": blackout_id,
                    "start": start,
                    "end": end
                })
                log.info(f"  Will remove blackout (ID: {blackout_id}): {start.time()} to {end.time()}")
        
        # Apply changes if --apply is set
        if args.apply:
            # Create new blackouts
            if blackouts_to_create:
                log.info(f"\nCreating {len(blackouts_to_create)} blackout(s)...")
                for blackout in blackouts_to_create:
                    try:
                        result = booked.create_blackout(
                            start_date=blackout["start"],
                            end_date=blackout["end"],
                            resource_ids=blackout["resource_ids"],
                            title=f"Tech Shift Blackout - {blackout['date']} {blackout['type']}",
                            description=f"Automated blackout: {blackout['reason']}"
                        )
                        log.info(f"  Created blackout: {blackout['date']} {blackout['type']} (ID: {result.get('blackoutId', 'N/A')})")
                    except Exception as e:
                        log.error(f"  Failed to create blackout for {blackout['date']} {blackout['type']}: {e}")
            
            # Remove unnecessary blackouts
            if blackouts_to_remove:
                log.info(f"\nRemoving {len(blackouts_to_remove)} blackout(s)...")
                for blackout in blackouts_to_remove:
                    try:
                        result = booked.delete_blackout(blackout["id"])
                        log.info(f"  Removed blackout (ID: {blackout['id']}): {blackout['start'].time()} to {blackout['end'].time()}")
                    except Exception as e:
                        log.error(f"  Failed to remove blackout (ID: {blackout['id']}): {e}")
        else:
            # Dry run - just log what would be done
            if blackouts_to_create:
                log.info(f"\nDry run: Would create {len(blackouts_to_create)} blackout(s)")
                for blackout in blackouts_to_create:
                    log.info(f"  Would create blackout for {blackout['date']} {blackout['type']}: {blackout['start'].time()} to {blackout['end'].time()}")
            
            if blackouts_to_remove:
                log.info(f"\nDry run: Would remove {len(blackouts_to_remove)} blackout(s)")
                for blackout in blackouts_to_remove:
                    log.info(f"  Would remove blackout (ID: {blackout['id']}): {blackout['start'].time()} to {blackout['end'].time()}")
            
            if not blackouts_to_create and not blackouts_to_remove:
                log.info(f"\nNo changes needed for {days_checked} days checked")
        
        # Output summary
        summary = {
            "days_checked": days_checked,
            "blackouts_to_create": len(blackouts_to_create),
            "blackouts_to_remove": len(blackouts_to_remove),
            "blackouts_created": [
                {
                    "date": b["date"],
                    "type": b["type"],
                    "start": b["start"].isoformat(),
                    "end": b["end"].isoformat(),
                    "reason": b["reason"]
                }
                for b in blackouts_to_create
            ] if args.apply else [],
            "blackouts_removed": [
                {
                    "id": b["id"],
                    "start": b["start"].isoformat(),
                    "end": b["end"].isoformat()
                }
                for b in blackouts_to_remove
            ] if args.apply else [],
            "dry_run": not args.apply,
        }
        
        print_yaml(summary)
