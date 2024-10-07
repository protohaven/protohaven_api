"""Helpers for testing policy enforcement methods"""

import datetime

from protohaven_api.config import tz

now = datetime.datetime.now().astimezone(tz)


TESTFEE = 5
TESTMEMBER = {"firstName": "testname", "id": "1111", "email1": "a@b.com"}


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
            "Close date (from Closure)": (
                [resolution.isoformat()] if resolution else None
            ),
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
            "Instance #": 12345,
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
