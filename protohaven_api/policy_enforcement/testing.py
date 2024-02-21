"""Helpers for testing policy enforcement methods"""
import datetime

import pytz

tz = pytz.timezone("EST")
now = datetime.datetime.now().astimezone(tz)


class Any:  # pylint: disable=too-few-public-methods
    """Matches any value - used for placeholder matching in asserts"""

    def __eq__(self, other):
        """Check for equality - always true"""
        return True


TESTFEE = 5
TESTMEMBER = {"firstName": "testname", "id": "1111"}


def violation(instance, onset, resolution=None, fee=TESTFEE, neon_id=TESTMEMBER["id"]):
    """Create test violation"""
    return {
        "id": instance,  # for testing, to simplify. This is actually an airtable id
        "fields": {
            "Instance #": instance,
            "Neon ID": neon_id,
            "Notes": "test violation notes",
            "Onset": onset.isoformat() if onset else None,
            "Closure": [True] if resolution else None,
            "Close date (from Closure)": [resolution.isoformat()]
            if resolution
            else None,
            "Daily Fee": fee,
        },
    }


def suspension(start, end=None, reinstated=None):
    """Create test suspension"""
    return {
        "id": "12345",  # For testing, to simplify. Actually an airtable ID
        "fields": {
            "Neon ID": TESTMEMBER["id"],
            "Start Date": start.isoformat(),
            "End Date": end.isoformat() if end else None,
            "Reinstated": reinstated,
        },
    }


def tfee(amt=5, created=now, vid="1234", paid=False):
    """Create a test fee"""
    return {
        "id": "testfee",
        "fields": {
            "Violation": [vid],
            "Created": created,
            "Amount": amt,
            "Paid": paid,
        },
    }


def dt(days):
    """Returns a date that is `days` away from now"""
    return now + datetime.timedelta(days=days)
