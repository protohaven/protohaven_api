"""Mock implementation of google services"""

from protohaven_api.config import safe_parse_datetime, tz
from protohaven_api.integrations import airtable_base


def get_calendar(_, time_min, time_max):
    """Mocks a fetch of calendar info using NocoDB data"""
    items = []
    time_min = time_min.astimezone(tz)
    time_max = time_max.astimezone(tz)
    for row in airtable_base.get_all_records("fake_google", "calendar"):
        start = safe_parse_datetime(row["fields"]["start"])
        end = safe_parse_datetime(row["fields"]["end"])
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
