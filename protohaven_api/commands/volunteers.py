"""Commands for alerting about empty (unstaffed) tech shifts"""

import logging

from protohaven_api.automation.techs import techs as forecast
from protohaven_api.commands.decorator import arg, command, print_yaml
from protohaven_api.config import tznow
from protohaven_api.integrations.comms import Msg

log = logging.getLogger("cli.volunteers")


class Commands:
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
            help="Shifts at least this many days away are planning (alert #tech-leads)",
            type=int,
            default=7,
        ),
    )
    def check_empty_shifts(self, args, _):
        """Check for shifts with zero techs on duty and prepare alerts.

        Empty shifts >= --planning-days away generate a message to #tech-leads.
        Empty shifts <= --urgent-days away generate a message to #techs.
        """
        now = tznow()
        data = forecast.generate(now, args.days_ahead, include_pii=False)

        # Build individual messages per empty shift for deduplication;
        # urgent #techs messages are yielded first, then #tech-leads.
        leads_msgs = []
        techs_msgs = []

        for i, day in enumerate(data["calendar_view"]):
            if day["is_holiday"]:
                continue

            for ap in ("AM", "PM"):
                shift = day[ap]
                if len(shift["people"]) == 0:
                    days_away = i
                    shift_info = {
                        "date": day["date"],
                        "shift": ap,
                        "days_away": days_away,
                    }
                    if days_away >= args.planning_days:
                        leads_msgs.append(
                            Msg.tmpl(
                                "empty_shift_leads",
                                id=f"empty_shift_leads_{day['date']}_{ap}",
                                shifts=[shift_info],
                                target="#tech-leads",
                            )
                        )
                    elif days_away <= args.urgent_days:
                        techs_msgs.append(
                            Msg.tmpl(
                                "empty_shift_techs",
                                id=f"empty_shift_techs_{day['date']}_{ap}",
                                shifts=[shift_info],
                                target="#techs",
                            )
                        )
                    else:
                        log.info(
                            f"Empty shift {day['date']} {ap} is {days_away} days "
                            f"away ({args.urgent_days + 1}-{args.planning_days - 1} "
                            "day gap); no alert generated"
                        )

        if techs_msgs:
            log.info(
                f"Found {len(techs_msgs)} empty shift(s) <= {args.urgent_days} "
                "days out for #techs"
            )
        if leads_msgs:
            log.info(
                f"Found {len(leads_msgs)} empty shift(s) >= {args.planning_days} "
                "days out for #tech-leads"
            )
        if not techs_msgs and not leads_msgs:
            log.info("No empty shifts found requiring alerts")

        # Urgent messages (#techs) before planning messages (#tech-leads)
        print_yaml(techs_msgs + leads_msgs)
