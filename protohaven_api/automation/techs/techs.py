"""Forecasting methods for shop tech shift staffing"""

import datetime
import logging
import re
from collections import defaultdict
from typing import NotRequired, Optional, TypedDict, cast

from holidays.countries.united_states import UnitedStates

from protohaven_api.integrations import airtable, neon
from protohaven_api.integrations.models import Member
from protohaven_api.rbac import Role

DEFAULT_FORECAST_LEN = 16

log = logging.getLogger("protohaven_api.automation.techs.techs")


class ProtohavenHolidays(UnitedStates):
    """Observed holidays for Protohaven, per our website
    https://www.protohaven.org/contact/
    """

    def _populate(self, year):
        self._year = year
        # See https://holidays.readthedocs.io/en/latest/examples
        # We explicitly *don't* prepopulate, as we want to opt in specific days
        self._add_holiday_dec_31("New Year's Eve")
        self._add_holiday_jan_1("New Year's Day")
        self._add_holiday_3rd_mon_of_jan("Martin Luther King Day")
        self._add_holiday_0_days_prior_easter("Easter Sunday")
        self._add_holiday_last_mon_of_may("Memorial Day")
        self._add_holiday_jun_19("Juneteenth")
        self._add_holiday_jul_4("Independence Day")
        self._add_holiday_1st_mon_of_sep("Labor Day")
        self._add_holiday_4th_thu_of_nov("Thanksgiving Day")
        self._add_holiday_1_day_past_4th_thu_of_nov("Day After Thanksgiving")
        self._add_holiday_dec_24("Christmas Eve")
        self._add_holiday_dec_25("Christmas Day")


ph_holidays = ProtohavenHolidays()


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


CalendarView = list[Day]


def _calendar_badge_color(num_people):
    """Returns the sveltestrap color tag for a badge given the number of attendant techs"""
    if num_people >= 3:
        return "success"
    if num_people == 2:
        return "info"
    if num_people == 1:
        return "warning"
    return "danger"


def _resolve_name_to_member(name: str) -> Member | None:
    """Resolve a tech name string to a Member object.
    Returns None if not found in Neon (guest tech)."""
    name = re.sub(r"\(.*\)", "", name)  # remove pronouns for matching purposes
    name = re.sub(r" +", " ", name)  # prevent double-space issues
    mm = list(neon.cached_find_best_match(name))
    log.info(f"Seeking match for tech {name}")
    for m in mm:
        # Checking with removed pronouns
        candidate = re.sub(r"\(.*\)", "", m.name).strip().lower()
        log.info(f"Candidate {candidate} vs {name.strip().lower()}")
        if candidate == name.strip().lower():
            return mm[0]
    return None


def _create_guest_member(name: str) -> Member:
    """Create a name-only Member object for a guest tech not found in Neon."""
    log.warning(
        f"Tech override not found in neon: {name}. Creating name-only Member object"
    )
    ns = [n.strip() for n in name.split(" ")][:2]
    return cast(
        Member,
        Member.from_neon_search(
            {
                "First Name": ns[0] if len(ns) > 0 else "",
                "Last Name": ns[1] if len(ns) > 1 else "",
            }
        ),
    )


def _is_delta_format(entries: list[str]) -> bool:
    """Detect if override entries use the delta format (prefixed with + or -).
    Returns True if any entry starts with + or -, indicating delta format.
    An empty list is treated as non-delta (no override)."""
    if not entries:
        return False
    return any(e.startswith("+") or e.startswith("-") for e in entries)


def _apply_delta_overrides(
    shift_people: list[Member], ovr_entries: list[str]
) -> list[Member]:
    """Apply delta-format overrides on top of shift_people.

    Entries are '+' for additions, '-' for removals."""
    result: list[Member] = list(shift_people)
    names_lower = {p.name.strip().lower() for p in result}

    for entry in ovr_entries:
        if not entry:
            continue
        prefix = entry[0]
        name = entry[1:].strip()
        raw_name = re.sub(r"\(.*\)", "", name).strip().lower()

        if prefix == "+" and raw_name not in names_lower:
            member = _resolve_name_to_member(name)
            if member is None:
                member = _create_guest_member(name)
            result.append(member)
            names_lower.add(raw_name)
        elif prefix == "-":
            result = [
                p
                for p in result
                if re.sub(r"\(.*\)", "", p.name).strip().lower() != raw_name
            ]
            names_lower = {
                re.sub(r"\(.*\)", "", p.name).strip().lower() for p in result
            }

    return result


def _resolve_legacy_overrides(ovr_entries: list[str]) -> list[Member]:
    """Resolve legacy (absolute) override entries into Member objects."""
    result: list[Member] = []
    for p in ovr_entries:
        p_clean = re.sub(r"\(.*\)", "", p)  # remove pronouns
        p_clean = re.sub(r" +", " ", p_clean)  # prevent double-space
        member = _resolve_name_to_member(p_clean)
        if member is None:
            member = _create_guest_member(p_clean)
        result.append(member)
    return result


def resolve_overrides(
    overrides: dict[str, airtable.ForecastOverride],
    shift: str,
    shift_people: list[Member],
) -> tuple[str | None, list[Member], str | None]:
    """Translate overrides into Member instances.

    Supports two formats:
    - Delta format (new): entries prefixed with '+' (additions) or '-' (removals).
      Applied on top of shift_people (the default techs for that shift).
      This ensures newly enrolled techs appear in previously-overridden shifts.
    - Legacy format: absolute list of tech names. Used directly as the final list.

    Special handling of "guest" techs if they do not exist in Neon.

    Note that caching must be used here as otherwise calendar views of
    forecasted tech dates slow to a crawl due to the number of one-off fetches."""
    ovr_id, ovr_entries, ovr_editor = overrides.get(shift) or (None, [], None)

    if not ovr_id or not ovr_entries:
        return None, [], None

    if _is_delta_format(ovr_entries):
        return ovr_id, _apply_delta_overrides(shift_people, ovr_entries), ovr_editor

    return ovr_id, _resolve_legacy_overrides(ovr_entries), ovr_editor


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

            # On holidays, we assume by default that nobody is on duty.
            people_in = shift_map.get((wd, ap), []) if d not in ph_holidays else []

            shift_people = []
            for p in people_in:  # remove if outside of the tech's tenure
                if (p.shop_tech_first_day is None or p.shop_tech_first_day <= d) and (
                    p.shop_tech_last_day is None or p.shop_tech_last_day >= d
                ):
                    shift_people.append(p)

            ovr_id, ovr_people, ovr_editor = resolve_overrides(
                overrides, f"{dstr} {ap}", shift_people
            )

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
            "is_holiday": d in ph_holidays,
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
