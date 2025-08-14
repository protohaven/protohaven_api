"""Forecasting methods for shop tech shift staffing"""

import datetime
import logging
from collections import defaultdict

import holidays

from protohaven_api.integrations import airtable, neon
from protohaven_api.integrations.models import Member
from protohaven_api.rbac import Role

DEFAULT_FORECAST_LEN = 16

log = logging.getLogger("protohaven_api.automation.techs.techs")

# Pylint seems to think `US()` doesn't exist. It may be dynamically loaded?
us_holidays = holidays.US()  # pylint: disable=no-member


def _calendar_badge_color(num_people):
    """Returns the sveltestrap color tag for a badge given the number of attendant techs"""
    if num_people >= 3:
        return "success"
    if num_people == 2:
        return "info"
    if num_people == 1:
        return "warning"
    return "danger"


def resolve_overrides(overrides, shift):
    """We must translate overrides into Member instances, with
    special handling of "guest" techs if they do not exist in Neon.

    Note that caching must be used here as otherwise calendar views of
    forecasted tech dates slow to a crawl due to the number of one-off fetches"""
    ovr_id, ovr_people, ovr_editor = overrides.get(shift) or (None, [], None)
    for i, p in enumerate(ovr_people):
        mm = list(neon.cache.find_best_match(p))
        found = False
        log.info(f"Seeking match for tech override {p}")
        for m in mm:
            log.info(f"Candidate {m.name} vs {p}")
            if m.name == p:
                ovr_people[i] = mm[0]
                found = True
                break

        if not found:
            log.warning(
                f"Tech override not found in neon: {p}. Creating name-only Member object"
            )
            ns = [n.strip() for n in p.split(" ")][:2]
            ovr_people[i] = Member.from_neon_search(
                {
                    "First Name": ns[0] if len(ns) > 0 else "",
                    "Last Name": ns[1] if len(ns) > 1 else "",
                }
            )
    return ovr_id, ovr_people, ovr_editor


def create_calendar_view(
    start_date, shift_map, overrides, forecast_len
):  # pylint: disable=too-many-locals, too-many-nested-blocks
    """Create a calendar view of tech shifts, respecting overrides and holidays"""
    calendar_view = []
    for i in range(forecast_len):
        d = start_date + datetime.timedelta(days=i)
        dstr = d.strftime("%Y-%m-%d")
        day = {"date": dstr}
        for ap in ["AM", "PM"]:
            wd = d.strftime("%A")

            ovr_id, ovr_people, ovr_editor = resolve_overrides(
                overrides, f"{dstr} {ap}"
            )

            # On holidays, we assume by default that nobody is on duty.
            people = shift_map.get((wd, ap), []) if d not in us_holidays else []

            final_people = []
            for p in people:  # remove if outside of the tech's tenure
                if (p.shop_tech_first_day is None or p.shop_tech_first_day <= d) and (
                    p.shop_tech_last_day is None or p.shop_tech_last_day >= d
                ):
                    final_people.append(p)

            shift = {
                "title": f"{d.strftime('%a %m/%d')} {ap}",
                "people": ovr_people if ovr_id else final_people,
                "id": f"Badge{i}{ap}",
            }
            shift["color"] = _calendar_badge_color(len(shift["people"]))
            if ovr_id:
                shift["ovr"] = {
                    "id": ovr_id,
                    "orig": final_people,
                    "editor": ovr_editor,
                }
            day[ap] = shift
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
    overrides = dict(airtable.get_forecast_overrides())
    techs = list(neon.search_members_with_role(Role.SHOP_TECH, tech_fields))
    shift_map = defaultdict(list)
    for t in techs:
        shift_map[t.shop_tech_shift].append(t)

    return {
        "calendar_view": create_calendar_view(date, shift_map, overrides, forecast_len),
    }
