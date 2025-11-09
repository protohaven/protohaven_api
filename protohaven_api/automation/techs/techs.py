"""Forecasting methods for shop tech shift staffing"""

import datetime
import logging
import re
from collections import defaultdict
from typing import NotRequired, Optional, TypedDict, cast

import holidays

from protohaven_api.integrations import airtable, neon
from protohaven_api.integrations.models import Member
from protohaven_api.rbac import Role

DEFAULT_FORECAST_LEN = 16

log = logging.getLogger("protohaven_api.automation.techs.techs")

us_holidays = holidays.country_holidays("US")


class ShiftOverride(TypedDict):
    """Data type for a shift override"""

    id: str
    orig: list[Member]
    editor: Optional[str]


class Shift(TypedDict):
    """Data type for a tech shift"""

    id: str
    title: str
    people: list[Member]
    color: str
    ovr: NotRequired[ShiftOverride]


class Day(TypedDict):
    """Data type for a day in the shift schedule"""

    date: str
    is_holiday: bool
    AM: Shift
    PM: Shift


type CalendarView = list[Day]


def _calendar_badge_color(num_people):
    """Returns the sveltestrap color tag for a badge given the number of attendant techs"""
    if num_people >= 3:
        return "success"
    if num_people == 2:
        return "info"
    if num_people == 1:
        return "warning"
    return "danger"


def resolve_overrides(
    overrides: dict[str, airtable.ForecastOverride], shift
) -> tuple[str | None, list[Member], str | None]:
    """We must translate overrides into Member instances, with
    special handling of "guest" techs if they do not exist in Neon.

    Note that caching must be used here as otherwise calendar views of
    forecasted tech dates slow to a crawl due to the number of one-off fetches"""
    ovr_id, ovr_people_in, ovr_editor = overrides.get(shift) or (None, [], None)
    ovr_people_out: list[Member] = []
    for p in ovr_people_in:
        p = re.sub(" +", " ", p)  # prevent double-space issues
        mm = list(neon.cache.find_best_match(p))
        found = False
        # log.info(f"Seeking match for tech override {p}")
        for m in mm:
            # log.info(f"Candidate {m.name} vs {p}")
            if m.name.strip().lower() == p.strip().lower():
                ovr_people_out.append(mm[0])
                found = True
                break

        if not found:
            log.warning(
                f"Tech override not found in neon: {p}. Creating name-only Member object"
            )
            ns = [n.strip() for n in p.split(" ")][:2]
            ovr_people_out.append(
                cast(
                    Member,
                    Member.from_neon_search(
                        {
                            "First Name": ns[0] if len(ns) > 0 else "",
                            "Last Name": ns[1] if len(ns) > 1 else "",
                        }
                    ),
                )
            )
    return ovr_id, ovr_people_out, ovr_editor


def create_calendar_view(  # pylint: disable=too-many-locals, too-many-nested-blocks
    start_date, shift_map, overrides, forecast_len
) -> CalendarView:
    """Create a calendar view of tech shifts, respecting overrides and holidays"""
    calendar_view: CalendarView = []
    for i in range(forecast_len):
        d = start_date + datetime.timedelta(days=i)
        dstr = d.strftime("%Y-%m-%d")

        shifts = {}

        for ap in ("AM", "PM"):
            wd = d.strftime("%A")

            ovr_id, ovr_people, ovr_editor = resolve_overrides(
                overrides, f"{dstr} {ap}"
            )

            # On holidays, we assume by default that nobody is on duty.
            people_in = shift_map.get((wd, ap), []) if d not in us_holidays else []

            shift_people = []
            for p in people_in:  # remove if outside of the tech's tenure
                if (p.shop_tech_first_day is None or p.shop_tech_first_day <= d) and (
                    p.shop_tech_last_day is None or p.shop_tech_last_day >= d
                ):
                    shift_people.append(p)

            final_people = ovr_people if ovr_id else shift_people

            shift: Shift = {
                "id": f"Badge{i}{ap}",
                "title": f"{d.strftime('%a %m/%d')} {ap}",
                "people": final_people,
                "color": _calendar_badge_color(len(final_people)),
            }

            if ovr_id:
                shift["ovr"] = {
                    "id": ovr_id,
                    "orig": shift_people,
                    "editor": ovr_editor,
                }

            shifts[ap] = shift

        day: Day = {
            "date": dstr,
            "is_holiday": d in us_holidays,
            "AM": shifts["AM"],
            "PM": shifts["PM"],
        }

        calendar_view.append(day)
    return calendar_view


def generate(date, forecast_len, include_pii=False):
    """Provide advance notice of the level of staffing of tech shifts"""
    tech_fields = [
        "First Name",
        neon.CustomField.AREA_LEAD,
        neon.CustomField.SHOP_TECH_SHIFT,
        neon.CustomField.SHOP_TECH_FIRST_DAY,
        neon.CustomField.SHOP_TECH_LAST_DAY,
    ]
    if include_pii:
        tech_fields += [
            "Last Name",
            "Preferred Name",
            neon.CustomField.PRONOUNS,
            "Email 1",
            neon.CustomField.CLEARANCES,
            neon.CustomField.INTEREST,
            neon.CustomField.EXPERTISE,
        ]

    date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    overrides = dict(airtable.get_forecast_overrides(include_pii))
    techs = list(neon.search_members_with_role(Role.SHOP_TECH, tech_fields))
    shift_map = defaultdict(list)
    for t in techs:
        shift_map[t.shop_tech_shift].append(t)

    return {
        "calendar_view": create_calendar_view(date, shift_map, overrides, forecast_len),
    }
