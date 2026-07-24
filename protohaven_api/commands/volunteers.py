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
    )
    def check_empty_shifts(self, args, _):
        """Check for shifts with zero techs on duty and prepare alerts.

        Empty shifts >= 7 days away generate a message to #tech-leads.
        Empty shifts <= 3 days away generate a message to #techs.
        """
        now = tznow()
        data = forecast.generate(now, args.days_ahead, include_pii=False)

        # Group empty shifts by target channel
        leads_shifts = []  # >= 7 days away -> #tech-leads
        techs_shifts = []  # <= 3 days away -> #techs

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
                    if days_away >= 7:
                        leads_shifts.append(shift_info)
                    elif days_away <= 3:
                        techs_shifts.append(shift_info)
                    else:
                        log.info(
                            f"Empty shift {day['date']} {ap} is {days_away} days "
                            "away (4-6 day gap); no alert generated"
                        )

        results = []
        if techs_shifts:
            log.info(
                f"Found {len(techs_shifts)} empty shift(s) <= 3 days out " "for #techs"
            )
            results.append(
                Msg.tmpl(
                    "empty_shift_techs",
                    id=f"empty_shift_techs_{'_'.join([t['date'] for t in techs_shifts])}",
                    shifts=techs_shifts,
                    target="#techs",
                )
            )

        if leads_shifts:
            log.info(
                f"Found {len(leads_shifts)} empty shift(s) >= 7 days out "
                "for #tech-leads"
            )
            results.append(
                Msg.tmpl(
                    "empty_shift_leads",
                    id=f"empty_shift_leads_{'_'.join([t['date'] for t in leads_shifts])}",
                    shifts=leads_shifts,
                    target="#tech-leads",
                )
            )

        if not results:
            log.info("No empty shifts found requiring alerts")

        print_yaml(results)
