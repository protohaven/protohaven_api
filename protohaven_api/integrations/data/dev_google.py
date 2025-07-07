"""Mock implementation of google services"""
from dateutil import parser as dateparser

from protohaven_api.config import tz
from protohaven_api.integrations import airtable_base


def get_calendar(_, time_min, time_max):
    """Mocks a fetch of calendar info using NocoDB data"""
    items = []
    time_min = time_min.astimezone(tz)
    time_max = time_max.astimezone(tz)
    for row in airtable_base.get_all_records("fake_google", "calendar"):
        start = dateparser.parse(row["fields"]["start"]).astimezone(tz)
        end = dateparser.parse(row["fields"]["end"]).astimezone(tz)
        if end < time_min or start > time_max:
            continue
        items.append(
            {
                "summary": row["fields"]["summary"],
                "start": {"dateTime": row["fields"]["start"]},
                "end": {"dateTime": row["fields"]["end"]},
            }
        )
    return {"items": items}
