"""Unit tests for builder module"""

import logging
from collections import namedtuple

import pytest
from protohaven_api.automation.classes import builder  # pylint: disable=import-error
from protohaven_api.config import safe_parse_datetime
from protohaven_api.testing import d, idfn

EVT_DAY = 30


@pytest.fixture(name="evt")
def _upcoming_event(mocker):
    a = mocker.MagicMock(
        fname="Test",
        email="test@attendee.com",
        neon_id=4567,
    )
    a.name = "Test Attendee"
    m = mocker.MagicMock(
        neon_id=1234,
        start_date=d(EVT_DAY, 18),
        end_date=d(EVT_DAY, 21),
        capacity=6,
        attendee_count=1,
        occupancy=1 / 6,
        in_blocklist=lambda: False,
        instructor_email="inst@ructor.com",
        instructor_fname="Test",
        volunteer=True,
        supply="Supply Check Needed",
        supply_cost=5,
        attendees=[a],
    )
    m.name = "Test Event"
    return m


def test_get_account_email(mocker):
    """Test email extraction"""
    mocker.patch.object(
        builder.neon_base,
        "fetch_account",
        return_value=mocker.MagicMock(email="foo@bar.com"),
    )
    assert builder.get_account_email("1234") == "foo@bar.com"


def test_get_unscheduled_instructors(mocker):
    """Test calendar reminder generation. This mostly replicates an equivalent test of the comms
    module but I'm including it here anyways."""
    mocker.patch(
        "protohaven_api.integrations.airtable.get_instructor_email_map",
        return_value={"Test Name": "test@email.com"},
    )
    mocker.patch.object(
        builder.airtable, "get_class_automation_schedule", return_value=[]
    )

    got = list(
        builder.get_unscheduled_instructors(
            safe_parse_datetime("2024-02-20"), safe_parse_datetime("2024-03-30")
        )
    )
    assert got[0] == ("Test Name", "test@email.com")


def test_gen_get_unscheduled_instructors_already_scheduled(mocker):
    """Test calendar reminder generation doesn't notify if already scheduled"""
    mocker.patch(
        "protohaven_api.integrations.airtable.get_instructor_email_map",
        return_value={"Test Name": "test@email.com"},
    )
    mocker.patch.object(
        builder.airtable,
        "get_class_automation_schedule",
        return_value=[
            {
                "fields": {
                    "Start Time": safe_parse_datetime("2024-02-21").isoformat(),
                    "Email": "TeSt@email.com",
                }
            }
        ],
    )

    got = list(
        builder.get_unscheduled_instructors(
            safe_parse_datetime("2024-02-20"), safe_parse_datetime("2024-03-30")
        )
    )
    assert len(got) == 0  # No emails, so no summary


def _mock_builder(  # pylint: disable=too-many-arguments
    mocker,
    upcoming_events=None,
    notifications_after_fn=lambda _neon_id, _date: {},
    get_account_email_fn=lambda _id: "test@attendee.com",
):
    mocker.patch(
        "protohaven_api.automation.classes.events.fetch_upcoming_events",
        return_value=upcoming_events,
    )
    mocker.patch(
        "protohaven_api.automation.classes.builder.get_account_email",
        side_effect=get_account_email_fn,
    )
    mocker.patch(
        "protohaven_api.integrations.airtable.get_notifications_after",
        side_effect=notifications_after_fn,
    )


def test_fetch_and_aggregate_data_empty(mocker):
    """Builder can handle an empty setup"""
    _mock_builder(mocker, upcoming_events=[])
    eb = builder.ClassEmailBuilder()
    eb.fetch_and_aggregate_data()
    assert not eb.events


Tc = namedtuple("Tc", "desc,now,evt_ovr,want")


@pytest.mark.parametrize(
    "tc",
    [
        Tc("no action (too far ahead)", d(0), {}, []),
        Tc(
            "post-run notifications",
            d(EVT_DAY + 1),
            {},
            [
                {
                    "id": 1234,
                    "target": "Instructor (inst@ructor.com)",
                    "subject": "Test Event: Please submit instructor log",
                },
                {
                    "id": 1234,
                    "target": "Test Attendee (test@attendee.com)",
                    "subject": "Test Event: Please share feedback",
                },
                {
                    "id": "N/A",
                    "target": "#class-automation",
                    "subject": "Automation notification summary",
                },
            ],
        ),
        Tc(
            "supply check",
            d(EVT_DAY - 8),
            {"supply_state": "Supply Check Needed"},
            [
                {
                    "id": 1234,
                    "target": "Instructor (inst@ructor.com)",
                    "subject": "Test Event on January 31 - please confirm class supplies",
                },
                {
                    "id": "N/A",
                    "target": "#class-automation",
                    "subject": "Automation notification summary",
                },
            ],
        ),
        Tc(
            "low attendance 7days",
            d(EVT_DAY - 7),
            {},
            [
                {
                    "id": 1234,
                    "target": "Instructor (inst@ructor.com)",
                    "subject": "Test Event on January 31 - help us find 5 more student(s)!",
                },
                {
                    "id": "N/A",
                    "target": "#class-automation",
                    "subject": "Automation notification summary",
                },
            ],
        ),
        Tc(
            "confirmed to run, no backfill",
            d(EVT_DAY - 1, 20),
            {"attendee_count": 6, "occupancy": 1.0},
            [
                {
                    "id": 1234,
                    "target": "Instructor (inst@ructor.com)",
                    "subject": "Test Event is on for January 31!",
                },
                {
                    "id": 1234,
                    "target": "Test Attendee (test@attendee.com)",
                    "subject": "Your class 'Test Event' is on for January 31!",
                },
                {
                    "id": "N/A",
                    "target": "#class-automation",
                    "subject": "Automation notification summary",
                },
            ],
        ),
        Tc(
            "confirmed to run, with techs backfill",
            d(EVT_DAY - 1, 20),
            {},
            [
                {
                    "id": 1234,
                    "target": "Instructor (inst@ructor.com)",
                    "subject": "Test Event is on for January 31!",
                },
                {
                    "id": 1234,
                    "target": "Test Attendee (test@attendee.com)",
                    "subject": "Your class 'Test Event' is on for January 31!",
                },
                {
                    "id": "1234",
                    "target": "#techs",
                    "subject": "New classes for tech backfill:",
                },
                {
                    "id": "N/A",
                    "target": "#class-automation",
                    "subject": "Automation notification summary",
                },
            ],
        ),
        # Tc("cancelled", d(EVT_DAY-1, 20), {"attendee_count": 0, "occupancy": 0}, [
        #     {
        #         "id": 1234,
        #         "target": "Instructor (inst@ructor.com)",
        #         "subject": "Your class 'Test Event' was canceled",
        #     },
        #     {
        #         "id": 1234,
        #         "target": "Test Attendee (test@attendee.com)",
        #         "subject": "Your class 'Test Event' was canceled",
        #     },
        #     {
        #         "id": "N/A",
        #         "target": "#class-automation",
        #         "subject": "Automation notification summary",
        #     },
        # ]),
    ],
    ids=idfn,
)
def test_builder_notifications(mocker, evt, caplog, tc):
    """Builder correctly builds notifiations at different times for a class with one attendee"""
    caplog.set_level(logging.INFO)
    for k, v in tc.evt_ovr.items():
        setattr(evt, k, v)

    _mock_builder(mocker, upcoming_events=[evt])
    eb = builder.ClassEmailBuilder()
    got = eb.build(tc.now)

    if not tc.want:
        assert not eb.actionable_classes
    else:
        got = [
            {k: v for k, v in dict(d).items() if k in ("id", "target", "subject")}
            for d in got
        ]
        assert got == tc.want


def test_builder_notified(mocker):
    """Tests that `notified` correctly returns True when comms have already been recently
    sent to a target"""
    eb = builder.ClassEmailBuilder()
    evt = mocker.MagicMock(start_date=d(0), neon_id=1234)

    # No notifications -> false
    assert eb.notified("test_target", evt, 1) is False

    # Noticication is true if within threshold days
    eb.notifications_by_class = {}
    eb.notifications_by_class[evt.neon_id] = {"test_target": [d(-2)]}
    assert eb.notified("test_target", evt, 3) is True
    assert eb.notified("test_target", evt, 1) is False


def test_gen_class_scheduled_alerts():
    """Test packaging and sending of class scheduling alerts"""
    scheduled_by_instructor = {
        "Instructor A": [
            {
                "fields": {
                    "Start Time": "2025-01-01 10:00:00",
                    "Name (from Class)": ["Class A"],
                    "Instructor": "Instructor A",
                    "Email": "a@a.com",
                }
            }
        ],
        "Instructor B": [
            {
                "fields": {
                    "Start Time": "2025-01-01 12:00:00",
                    "Name (from Class)": ["Class B"],
                    "Instructor": "Instructor B",
                    "Email": "b@b.com",
                }
            }
        ],
    }
    got = [dict(m) for m in builder.gen_class_scheduled_alerts(scheduled_by_instructor)]

    assert got[0]["target"] == "a@a.com"
    assert "teach 1" in got[0]["subject"]
    assert "Jan 01 2025, 10am: Class A" in got[0]["body"]
    assert got[1]["target"] == "b@b.com"
    assert "teach 1" in got[1]["subject"]
    assert "Jan 01 2025, 12pm: Class B" in got[1]["body"]
    assert got[2]["target"] == "#instructors"
    assert got[3]["target"] == "#class-automation"
    assert len(got) == 4
