"""Commands for alerting about empty (unstaffed) tech shifts"""

import argparse
import logging

from protohaven_api.automation.techs import techs as forecast
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import safe_parse_datetime, tznow
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.volunteers")


class Commands:  # pylint: disable=too-few-public-methods
    """Commands for managing volunteer shift alerts and scheduling"""

    @command(
        arg(
            "--days-ahead",
            help="Number of days into the future to check for empty shifts",
            type=int,
            default=14,
        ),
        arg(
            "--urgent-days",
            help="Shifts within this many days are urgent (alert #techs)",
            type=int,
            default=3,
        ),
        arg(
            "--planning-days",
            help="Shifts between --urgent-days and this many days out (alert #tech-leads)",
            type=int,
            default=7,
        ),
        arg(
            "--dedupe",
            help="Assign IDs to messages so that repeat runs do not cause duplicates/spam",
            action=argparse.BooleanOptionalAction,
            default=True,
        ),
        arg(
            "--start",
            help="Start date for checking shifts (default now)",
            type=str,
            default=None,
        ),
    )
    def check_empty_shifts(self, args, _):
        """Check for shifts with zero techs on duty and prepare alerts.

        Empty shifts <= --urgent-days away generate a message to #techs.
        Empty shifts > --urgent-days and <= --planning-days away
        generate a message to #tech-leads.
        Shifts beyond --planning-days are ignored.
        """
        now = tznow() if not args.start else safe_parse_datetime(args.start)
        data = forecast.generate(now, args.days_ahead, include_pii=True)

        # Build individual messages per empty shift for deduplication;
        # urgent #techs messages are yielded first, then #tech-leads.
        # expected closure holidays notify #staff
        leads_msgs = []
        techs_msgs = []
        staff_msgs = []

        for i, day in enumerate(data["calendar_view"]):
            for ap in ("AM", "PM"):
                shift = day[ap]
                log.info(f"{day['date']} {ap}: {len(shift['people'])} on duty")
                if len(shift["people"]) == 0:
                    days_away = i
                    shift_info = {
                        "date": day["date"],
                        "shift": ap,
                        "days_away": days_away,
                    }
                    if day["is_holiday"]:
                        if days_away <= args.planning_days:
                            staff_msgs.append(
                                Msg.tmpl(
                                    "empty_shift_staff",
                                    id=(
                                        f"empty_shift_holiday_{day['date']}_{ap}"
                                        if args.dedupe
                                        else None
                                    ),
                                    shift=shift_info,
                                    target="#staff",
                                )
                            )
                    elif days_away <= args.urgent_days:
                        techs_msgs.append(
                            Msg.tmpl(
                                "empty_shift_techs",
                                id=(
                                    f"empty_shift_techs_{day['date']}_{ap}"
                                    if args.dedupe
                                    else None
                                ),
                                shift=shift_info,
                                target="#techs",
                            )
                        )
                    elif days_away <= args.planning_days:
                        leads_msgs.append(
                            Msg.tmpl(
                                "empty_shift_leads",
                                id=(
                                    f"empty_shift_leads_{day['date']}_{ap}"
                                    if args.dedupe
                                    else None
                                ),
                                shift=shift_info,
                                target="#tech-leads",
                            )
                        )
                    else:
                        log.info(
                            f"Empty shift {day['date']} {ap} is {days_away} days "
                            f"away (beyond --planning-days={args.planning_days}); "
                            "no alert generated"
                        )

        if techs_msgs:
            log.info(
                f"Found {len(techs_msgs)} empty shift(s) <= {args.urgent_days} "
                "days out for #techs"
            )
        if leads_msgs:
            log.info(
                f"Found {len(leads_msgs)} empty shift(s) > {args.urgent_days} "
                f"and <= {args.planning_days} days out for #tech-leads"
            )
        if staff_msgs:
            log.info(
                f"Found {len(staff_msgs)} empty shift(s) on holidays < {args.planning_days} "
                f"days out for #staff"
            )

        if not techs_msgs and not leads_msgs and not staff_msgs:
            log.info("No empty shifts found requiring alerts")

        # Urgent messages (#techs) before planning messages (#tech-leads)
        print_yaml(techs_msgs + leads_msgs + staff_msgs)
