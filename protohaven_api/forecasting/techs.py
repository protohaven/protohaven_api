"""Forecasting methods for shop tech shift staffing"""
import datetime
from collections import defaultdict

from dateutil import parser as dateparser

from protohaven_api.config import tz
from protohaven_api.integrations import airtable, neon

DEFAULT_FORECAST_LEN = 16


def get_shift_map():
    """Get map of shift name to list of techs on shift"""
    techs = neon.fetch_techs_list()
    shift_map = defaultdict(list)
    for t in techs:
        if not t.get("shift"):
            continue
        for s in t.get("shift").split(","):
            s = s.strip()
            shift_map[s].append(t["name"])
    return dict(shift_map)


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
    start_date, shift_map, shift_term_map, time_off, forecast_len
):  # pylint: disable=too-many-locals, too-many-nested-blocks
    # This can be simplified after overrides have been rolled out; we can
    # remove the time_off lookup
    calendar_view = []
    overrides = dict(airtable.get_forecast_overrides())
    for i in range(forecast_len):
        day_view = []
        d = start_date + datetime.timedelta(days=i)
        for ap in ["AM", "PM"]:
            dstr = d.strftime("%Y-%m-%d")
            s = f"{d.strftime('%A')} {ap}"

            ovr, ovr_people, ovr_editor = overrides.get(
                f"{dstr} {ap}", (None, None, None)
            )

            people = shift_map.get(s, [])
            for cov in time_off:
                if cov["fields"]["Date"] == dstr and cov["fields"]["Shift"] == ap:
                    people = [p for p in people if p != cov["fields"]["Shop Tech"]]
                    if cov["fields"].get("Covered By"):
                        people.append(cov["fields"]["Covered By"])
            final_people = []
            for p in people:  # remove if outside of the tech's tenure
                first_day, last_day = shift_term_map.get(p, (None, None))
                if (first_day is None or first_day <= d) and (
                    last_day is None or last_day >= d
                ):
                    final_people.append(p)

            day = {
                "ap": ap,
                "date": dstr,
                "title": f"{d.strftime('%a %m/%d')} {ap}",
                "people": ovr_people or final_people,
                "id": f"Badge{i}{ap}",
            }
            day["color"] = _calendar_badge_color(len(day["people"]))
            if ovr:
                day["ovr"] = {"id": ovr, "orig": final_people, "editor": ovr_editor}
            day_view.append(day)
        calendar_view.append(day_view)
    return calendar_view


def generate(date, forecast_len):
    """Provide advance notice of the level of staffing of tech shifts"""
    date = date.replace(hour=0, minute=0, second=0, microsecond=0)
    shift_term_map = {
        t["name"]: (
            dateparser.parse(t["first_day"])
            .astimezone(tz)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            if t.get("first_day") is not None
            else None,
            dateparser.parse(t["last_day"])
            .astimezone(tz)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            if t.get("last_day") is not None
            else None,
        )
        for t in neon.fetch_techs_list()
    }
    shift_map = get_shift_map()

    time_off = [
        t
        for t in airtable.get_shop_tech_time_off()
        if t["fields"].get("Date")
        and dateparser.parse(t["fields"]["Date"]).astimezone(tz) >= date
    ]
    time_off.sort(key=lambda t: dateparser.parse(t["fields"]["Date"]))

    coverage_missing = []
    coverage_ok = []
    for cov in time_off:
        if cov["fields"].get("Covered By", None) is not None:
            coverage_ok.append(cov)
        else:
            coverage_missing.append(cov)

    calendar_view = _create_calendar_view(
        date, shift_map, shift_term_map, time_off, forecast_len
    )
    return {
        "calendar_view": calendar_view,
        "coverage_missing": coverage_missing,
        "coverage_ok": coverage_ok,
    }
