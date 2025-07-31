"""Dev environment mock of discord functionality"""

from protohaven_api.config import safe_parse_datetime
from protohaven_api.integrations import airtable_base


class Response:  # pylint: disable=too-few-public-methods
    """Discord response in dev mode"""

    def raise_for_status(self):
        """Do nothing; stub only"""


def get_all_members():
    """Return fake data from Nocodb"""
    for row in airtable_base.get_all_records("fake_discord", "members"):
        yield (
            row["fields"]["name"],
            row["fields"]["display_name"],
            safe_parse_datetime(row["fields"]["joined_at"]),
            [(a, a) for a in row["fields"]["roles"].split(",")],
        )


def resolve_user_id(name):
    """Resolve user ID from display name"""
    for row in airtable_base.get_all_records("fake_discord", "members"):
        if name in (row["fields"]["name"], row["fields"]["display_name"]):
            return row["id"]
    return None


def get_member_channels():
    """Fetches all channels with members role"""
    result = []
    for row in airtable_base.get_all_records("fake_discord", "channels"):
        if "Members" not in row["fields"]["roles"]:
            continue
        result.append((row["id"], row["fields"]["name"]))
    return result
