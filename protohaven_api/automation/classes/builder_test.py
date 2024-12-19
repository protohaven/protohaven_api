"""Unit tests for builder module"""
import logging

from dateutil.parser import parse as parse_date

from protohaven_api.automation.classes import builder  # pylint: disable=import-error
from protohaven_api.config import tz  # pylint: disable=import-error

TEST_NOW = parse_date("2024-02-22").astimezone(tz)


def test_get_account_email(mocker):
    """Test email extraction"""
    mocker.patch.object(
        builder.neon_base,
        "fetch_account",
        return_value=({"primaryContact": {"email2": "foo@bar.com"}}, False),
    )
    assert builder.get_account_email("1234") == "foo@bar.com"


def test_get_account_email_unset(mocker):
    """Test email extraction when there is no email to extract"""
    mocker.patch.object(
        builder.neon_base, "fetch_account", return_value=({"primaryContact": {}}, False)
    )
    assert not builder.get_account_email("1234")


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
            parse_date("2024-02-20"), parse_date("2024-03-30")
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
                    "Start Time": parse_date("2024-02-21").isoformat(),
                    "Email": "TeSt@email.com",
                }
            }
        ],
    )

    got = list(
        builder.get_unscheduled_instructors(
            parse_date("2024-02-20"), parse_date("2024-03-30")
        )
    )
    assert len(got) == 0  # No emails, so no summary


def _mock_builder(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    mocker,
    airtable_schedule,
    neon_events,
    fetch_attendees_fn=lambda _id: [],
    notifications_after_fn=lambda _neon_id, _date: {},
    get_account_email_fn=lambda _id: None,
):
    mocker.patch(
        "protohaven_api.integrations.airtable.get_class_automation_schedule",
        return_value=airtable_schedule,
    )
    mocker.patch(
        "protohaven_api.integrations.neon.fetch_upcoming_events",
        return_value=neon_events,
    )
    mocker.patch(
        "protohaven_api.integrations.neon.fetch_attendees",
        side_effect=fetch_attendees_fn,
    )
    mocker.patch(
        "protohaven_api.automation.classes.builder.get_account_email",
        side_effect=get_account_email_fn,
    )
    mocker.patch(
        "protohaven_api.integrations.airtable.get_notifications_after",
        side_effect=notifications_after_fn,
    )


def _mock_builder_singles(mocker, airtable_fields, neon_event):
    """Mocks out neon and airtable to return a single event with a single attendee"""
    return _mock_builder(
        mocker,
        airtable_schedule=[{"fields": airtable_fields}],
        neon_events=[neon_event],
        fetch_attendees_fn=lambda _id: [
            {
                "registrationStatus": "SUCCEEDED",
                "accountId": 4567,
                "firstName": "Test",
                "lastName": "Attendee",
                "attendeeId": 4567,
            }
        ],
        get_account_email_fn=lambda _id: "test@attendee.com",
    )


def test_builder_fetch_aggregate_empty(mocker):
    """Builder can handle an empty setup"""
    _mock_builder(mocker, airtable_schedule=[], neon_events=[])
    eb = builder.ClassEmailBuilder(use_cache=False)
    eb.fetch_and_aggregate_data(TEST_NOW)
    assert eb.airtable_schedule == {}
    assert eb.events == []


def _airtable_schedule():
    return {
        "1234": {
            "fields": {
                "Neon ID": "1234",
                "Instructor": "Test Instructor",
                "Email": "inst@ructor.com",
                "Volunteer": True,
                "Supply State": "Supply Check Needed",
                "Supply Cost (from Class)": [5],
            }
        }
    }


def _neon_events():
    return [
        {
            "id": 1234,
            "name": "Test Event",
            "startDate": "2024-02-20",
            "startTime": "06:00pm",
            "endDate": "2024-02-20",
            "endTime": "09:00pm",
            "capacity": 6,
            "python_date": parse_date("2024-02-20 18:00").astimezone(tz),
            "python_date_end": parse_date("2024-02-20 21:00").astimezone(tz),
            "attendees": [
                {
                    "registrationStatus": "SUCCEEDED",
                    "accountId": 4567,
                    "firstName": "Test",
                    "lastName": "Attendee",
                    "attendeeId": 4567,
                    "email": "test@attendee.com",
                }
            ],
            "signups": 1,
            "occupancy": 0.16666666666666666,
            "need": 2,
            "instructor_email": "inst@ructor.com",
            "instructor_firstname": "Test",
            "volunteer_instructor": True,
            "supply_state": "Supply Check Needed",
            "supply_cost": 5,
            "notifications": {},
        }
    ]


def test_builder_fetch_aggregate_singletons(mocker, caplog):
    """Builder correctly aggregates data from Airtable and Neon for a class with
    a single attendee"""
    caplog.set_level(logging.INFO)

    _mock_builder_singles(
        mocker,
        airtable_fields={
            "Neon ID": "1234",
            "Instructor": "Test Instructor",
            "Email": "inst@ructor.com",
            "Volunteer": True,
            "Supply State": "Supply Check Needed",
            "Supply Cost (from Class)": [5],
        },
        neon_event={
            "id": 1234,
            "name": "Test Event",
            "startDate": "2024-02-20",
            "startTime": "06:00pm",
            "endDate": "2024-02-20",
            "endTime": "09:00pm",
            "capacity": 6,
        },
    )
    eb = builder.ClassEmailBuilder(use_cache=False)
    eb.fetch_and_aggregate_data(TEST_NOW)
    assert eb.airtable_schedule == _airtable_schedule()
    evt = _neon_events()[0]
    assert eb.events == [evt]

    # Actionable class assignment happens when event is sorted
    eb._sort_event_for_notification(  # pylint: disable=protected-access
        eb.events[0], parse_date("2024-02-21").astimezone(tz)
    )
    assert eb.actionable_classes == [[evt, builder.Action.POST_RUN_SURVEY]]


def test_builder_no_actionable_classes(mocker, caplog):
    """Builder does not create an action if the class is too far out"""
    caplog.set_level(logging.INFO)
    _mock_builder_singles(
        mocker,
        airtable_fields={
            "Neon ID": "1234",
            "Instructor": "Test Instructor",
            "Email": "inst@ructor.com",
            "Volunteer": True,
            "Supply State": "Supply Check Needed",
            "Supply Cost (from Class)": [5],
        },
        neon_event={
            "id": 1234,
            "name": "Test Event",
            "startDate": "2024-03-20",  # Date in far future
            "startTime": "06:00pm",
            "endDate": "2024-03-20",
            "endTime": "09:00pm",
            "capacity": 6,
        },
    )
    eb = builder.ClassEmailBuilder(use_cache=False)
    eb.fetch_and_aggregate_data(TEST_NOW)
    assert len(eb.events) > 0

    # Actionable class assignment happens when event is sorted
    eb._sort_event_for_notification(  # pylint: disable=protected-access
        eb.events[0], parse_date("2024-02-21").astimezone(tz)
    )
    assert not eb.actionable_classes


def _gen_actionable_class(action, cid=1234):
    return (
        {
            "id": cid,
            "name": "Test Event",
            "python_date": parse_date("2024-02-20").astimezone(tz),
            "instructor_email": "inst@ructor.com",
            "notifications": {},
            "instructor_firstname": "Instructor",
            "capacity": 6,
            "signups": 2,
            "need": 1,
            "occupancy": 2 / 6,
            "attendees": [
                {
                    "registrationStatus": "SUCCEEDED",
                    "accountId": 4567,
                    "firstName": "Test",
                    "lastName": "Attendee",
                    "attendeeId": 4567,
                    "email": "test@attendee.com",
                }
            ],
        },
        action,
    )


def test_builder_post_run_survey(caplog):
    """Builds instructor log reminder, attendee feedback email,
    and summary when the class is over"""
    caplog.set_level(logging.DEBUG)
    eb = builder.ClassEmailBuilder()
    eb.fetch_and_aggregate_data = lambda now: None
    eb.actionable_classes = [_gen_actionable_class(builder.Action.POST_RUN_SURVEY)]
    got = [
        {k: v for k, v in dict(d).items() if k in ("id", "target", "subject")}
        for d in eb.build(TEST_NOW)
    ]
    assert got == [
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
    ]


def test_builder_supply_check(caplog):
    """Instructor is asked to check supplies"""
    caplog.set_level(logging.DEBUG)
    eb = builder.ClassEmailBuilder()
    eb.fetch_and_aggregate_data = lambda now: None
    eb.actionable_classes = [_gen_actionable_class(builder.Action.SUPPLY_CHECK_NEEDED)]

    got = [
        {k: v for k, v in dict(d).items() if k in ("id", "target", "subject")}
        for d in eb.build(TEST_NOW)
    ]
    assert got == [
        {
            "id": 1234,
            "target": "Instructor (inst@ructor.com)",
            "subject": "Test Event on February 20 - please confirm class supplies",
        },
        {
            "id": "N/A",
            "target": "#class-automation",
            "subject": "Automation notification summary",
        },
    ]


def test_builder_low_attendance_7days(caplog):
    """Instructor is notified when attendance is low"""
    caplog.set_level(logging.DEBUG)
    eb = builder.ClassEmailBuilder()
    eb.fetch_and_aggregate_data = lambda now: None
    eb.actionable_classes = [_gen_actionable_class(builder.Action.LOW_ATTENDANCE_7DAYS)]
    got = [
        {k: v for k, v in dict(d).items() if k in ("id", "target", "subject")}
        for d in eb.build(TEST_NOW)
    ]
    assert got == [
        {
            "id": 1234,
            "target": "Instructor (inst@ructor.com)",
            "subject": "Test Event on February 20 - help us find 4 more student(s)!",
        },
        {
            "id": "N/A",
            "target": "#class-automation",
            "subject": "Automation notification summary",
        },
    ]


def test_builder_confirm(caplog):
    """Instructor and attendee are notified when class is confirmed to run"""
    caplog.set_level(logging.DEBUG)
    eb = builder.ClassEmailBuilder()
    eb.fetch_and_aggregate_data = lambda now: None
    eb.actionable_classes = [_gen_actionable_class(builder.Action.CONFIRM)]
    got = [
        {k: v for k, v in dict(d).items() if k in ("id", "target", "subject")}
        for d in eb.build(TEST_NOW)
    ]
    assert got == [
        {
            "id": 1234,
            "target": "Instructor (inst@ructor.com)",
            "subject": "Test Event is on for February 20!",
        },
        {
            "id": 1234,
            "target": "Test Attendee (test@attendee.com)",
            "subject": "Your class 'Test Event' is on for February 20!",
        },
        {
            "id": "N/A",
            "target": "#class-automation",
            "subject": "Automation notification summary",
        },
    ]


def test_builder_cancel(caplog):
    """Instructor and attendee are notified when class is canceled"""
    caplog.set_level(logging.DEBUG)
    eb = builder.ClassEmailBuilder()
    eb.fetch_and_aggregate_data = lambda now: None
    eb.actionable_classes = [_gen_actionable_class(builder.Action.CANCEL)]
    got = [
        {k: v for k, v in dict(d).items() if k in ("id", "target", "subject")}
        for d in eb.build(TEST_NOW)
    ]
    assert got == [
        {
            "id": 1234,
            "target": "Instructor (inst@ructor.com)",
            "subject": "Your class 'Test Event' was canceled",
        },
        {
            "id": 1234,
            "target": "Test Attendee (test@attendee.com)",
            "subject": "Your class 'Test Event' was canceled",
        },
        {
            "id": "N/A",
            "target": "#class-automation",
            "subject": "Automation notification summary",
        },
    ]


def test_builder_techs():
    """Tests generation of class comms to techs"""
    eb = builder.ClassEmailBuilder()
    eb.fetch_and_aggregate_data = lambda now: None
    c3 = _gen_actionable_class(builder.Action.FOR_TECHS, cid=5678)
    c3[0]["notifications"] = {"#techs": [TEST_NOW]}
    eb.actionable_classes = [
        _gen_actionable_class(builder.Action.FOR_TECHS, cid=1234),
        _gen_actionable_class(builder.Action.FOR_TECHS, cid=5678),
        c3,  # Gets ignored due to prior notification
    ]
    got = [
        {k: v for k, v in dict(d).items() if k in ("id", "target", "subject")}
        for d in eb.build(TEST_NOW)
    ]
    assert got == [
        {
            "id": "1234,5678",
            "target": "#techs",
            "subject": "New classes for tech backfill:",
        },
        {
            "id": "N/A",
            "target": "#class-automation",
            "subject": "Automation notification summary",
        },
    ]


def test_builder_notified():
    """Tests that `notified` correctly returns True when comms have already been recently
    sent to a target"""
    eb = builder.ClassEmailBuilder()
    start = parse_date("2024-02-03")
    assert (
        eb.notified(
            "test_target",
            {
                "python_date": start,
                "notifications": {"test_target": [parse_date("2024-02-01")]},
            },
            2,
        )
        is True
    )
    assert (
        eb.notified(
            "test_target",
            {
                "python_date": start,
                "notifications": {"test_target": [parse_date("2024-02-01")]},
            },
            1,
        )
        is False
    )
    assert (
        eb.notified("test_target", {"python_date": start, "notifications": {}}, 2)
        is False
    )
