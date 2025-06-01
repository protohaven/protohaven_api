"""Forecasting methods for shop tech shift staffing"""
import datetime
from collections import defaultdict

from protohaven_api.integrations import airtable, neon
from protohaven_api.rbac import Role

DEFAULT_FORECAST_LEN = 16


def _calendar_badge_color(num_people):
    """Returns the sveltestrap color tag for a badge given the number of attendant techs"""
    if num_people >= 3:
        return "success"
    if num_people == 2:
        return "info"
    if num_people == 1:
        return "warning"
    return "danger"


def _create_calendar_view(
    start_date, shift_map, forecast_len
):  # pylint: disable=too-many-locals, too-many-nested-blocks
    calendar_view = []
    overrides = dict(airtable.get_forecast_overrides())
    for i in range(forecast_len):
        d = start_date + datetime.timedelta(days=i)
        dstr = d.strftime("%Y-%m-%d")
        day = {"date": dstr}
        for ap in ["AM", "PM"]:
            s = f"{d.strftime('%A')} {ap}"

            ovr, ovr_people, ovr_editor = overrides.get(
                f"{dstr} {ap}", (None, None, None)
            )
            for i, p in enumerate(ovr_people):
                fname, lname = [n.strip() for n in p.split(" ")][:2]
                mm = neon.search_members_by_name(fname, lname, also_fetch=True)
                if len(mm) != 1:
                    raise RuntimeError(
                        "Multiple member matches for Neon lookup of tech override {p}"
                    )
                ovr_people[i] = mm[0]

            people = shift_map.get(s, [])
            final_people = []
            for p in people:  # remove if outside of the tech's tenure
                if (p.shop_tech_first_day is None or p.shop_tech_first_day <= d) and (
                    p.shop_tech_last_day is None or p.shop_tech_last_day >= d
                ):
                    final_people.append(p)

            shift = {
                "title": f"{d.strftime('%a %m/%d')} {ap}",
                "people": ovr_people or final_people,
                "id": f"Badge{i}{ap}",
            }
            shift["color"] = _calendar_badge_color(len(shift["people"]))
            if ovr:
                shift["ovr"] = {"id": ovr, "orig": final_people, "editor": ovr_editor}
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
    techs = list(neon.search_members_with_role(Role.SHOP_TECH, tech_fields))
    shift_map = defaultdict(list)
    for t in techs:
        shift_map[t.shop_tech_shift].append(t)

    return {
        "calendar_view": _create_calendar_view(date, shift_map, forecast_len),
    }
