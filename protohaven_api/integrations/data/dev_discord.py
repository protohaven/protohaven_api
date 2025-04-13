"""Dev environment mock of discord functionality"""

from dateutil import parser as dateparser

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
            dateparser.parse(row["fields"]["joined_at"]),
            [(a, a) for a in row["fields"]["roles"].split(",")],
        )
