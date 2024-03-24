"""Verify proper behavior of instructor pages"""
import datetime

from protohaven_api.handlers.instructor import *


def test_class_no_clearances():
    """Ensure that a class without clearances still loads the page."""


TEST_EMAIL = "test@email.com"
now = datetime.datetime.now()


def dt(days=0, hours=0):
    return now + datetime.timedelta(days=days, hours=hours)


def _sched(id, email=TEST_EMAIL, start=now, days=1, confirmed=None):
    return {
        "id": id,
        "fields": {
            "Email": email,
            "Start Time": start.isoformat(),
            "Confirmed": None if not confirmed else confirmed.isoformat(),
            "Days (from Class)": [days],
        },
    }


def test_dashboard_schedule(mocker):
    mocker.patch(
        "protohaven_api.integrations.airtable.get_class_automation_schedule",
        return_value=[
            _sched(
                "Unconfirmed, too close HIDDEN",
                confirmed=None,
                start=dt(HIDE_UNCONFIRMED_DAYS_AHEAD - 1),
            ),
            _sched(
                "Unconfirmed, not too close",
                confirmed=None,
                start=dt(HIDE_UNCONFIRMED_DAYS_AHEAD + 1),
            ),
            _sched(
                "Confirmed, too old HIDDEN",
                confirmed=now,
                start=dt(-HIDE_CONFIRMED_DAYS_AFTER - 1),
            ),
            _sched(
                "Confirmed, after run, not too old",
                confirmed=now,
                start=dt(-HIDE_CONFIRMED_DAYS_AFTER + 1),
            ),
            _sched("Bad email", confirmed=now, start=now, email="bad@bad.com"),
        ],
    )
    got = {g[0] for g in get_dashboard_schedule_sorted(TEST_EMAIL)}
    assert got == {"Unconfirmed, not too close", "Confirmed, after run, not too old"}
