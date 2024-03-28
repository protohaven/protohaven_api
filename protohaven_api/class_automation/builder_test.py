"""Unit tests for builder module"""
import logging

from dateutil.parser import parse as parse_date

from protohaven_api.class_automation import builder  # pylint: disable=import-error
from protohaven_api.class_automation.testdata import (  # pylint: disable=import-error
    assert_matches_testdata,
)

TEST_NOW = parse_date("2024-02-22")


def test_get_account_email_individual(mocker):
    """Test email extraction from individual account"""
    mocker.patch(
        "protohaven_api.integrations.neon.fetch_account",
        return_value={
            "individualAccount": {"primaryContact": {"email2": "foo@bar.com"}}
        },
    )
    assert builder.get_account_email("1234") == "foo@bar.com"


def test_get_account_email_company(mocker):
    """Test email extraction from company account"""
    mocker.patch(
        "protohaven_api.integrations.neon.fetch_account",
        return_value={"companyAccount": {"primaryContact": {"email2": "foo@bar.com"}}},
    )
    assert builder.get_account_email("1234") == "foo@bar.com"


def test_get_account_email_unset(mocker):
    """Test email extraction when there is no email to extract"""
    mocker.patch(
        "protohaven_api.integrations.neon.fetch_account",
        return_value={"individualAccount": {"primaryContact": {}}},
    )
    assert not builder.get_account_email("1234")


def test_gen_calendar_reminders(mocker):
    """Test calendar reminder generation. This mostly replicates an equivalent test of the comms
    module but I'm including it here anyways."""
    mocker.patch(
        "protohaven_api.integrations.airtable.get_instructor_email_map",
        return_value={"Test Name": "test@email.com"},
    )
    got = builder.gen_calendar_reminders(
        parse_date("2024-02-20"), parse_date("2024-03-30")
    )
    assert len(got) == 2  # Email and summary
    assert got[0]["subject"] == "Test: please confirm your teaching availability!"
    assert_matches_testdata(got[0]["body"], "test_gen_calendar_reminders.txt")


def _mock_builder(  # pylint: disable=too-many-arguments
    mocker,
    airtable_schedule,
    neon_events,
    fetch_attendees_fn=lambda _id: [],
    emails_notified_after_fn=lambda _neon_id, _date: [],
    get_account_email_fn=lambda _id: None,
    now=TEST_NOW,
):
    mocker.patch(
        "protohaven_api.integrations.airtable.get_class_automation_schedule",
        return_value=airtable_schedule,
    )
    mocker.patch(
        "protohaven_api.integrations.neon.fetch_published_upcoming_events",
        return_value=neon_events,
    )
    mocker.patch(
        "protohaven_api.integrations.neon.fetch_attendees",
        side_effect=fetch_attendees_fn,
    )
    mocker.patch(
        "protohaven_api.class_automation.builder.get_account_email",
        side_effect=get_account_email_fn,
    )
    mocker.patch(
        "protohaven_api.integrations.airtable.get_emails_notified_after",
        side_effect=emails_notified_after_fn,
    )

    # Discard message body for all built messages (tested elsewhere)
    return [
        {"id": r["id"], "target": r["target"], "subject": r["subject"]}
        for r in builder.ClassEmailBuilder(use_cache=False).build(now)
    ]


def _mock_builder_singles(mocker, airtable_fields, neon_event, now=TEST_NOW):
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
        now=now,
    )


def test_builder_empty(mocker):
    """Builder can handle an empty setup"""
    got = _mock_builder(mocker, airtable_schedule=[], neon_events=[])
    assert got == []


TEST_AIRTABLE = {
    "Neon ID": "1234",
    "Instructor": "Test Instructor",
    "Email": "inst@ructor.com",
    "Volunteer": True,
    "Supply State": "Supply Check Needed",
}
TEST_NEON = {
    "id": 1234,
    "name": "Test Event",
    "startDate": "2024-02-20",
    "startTime": "06:00pm",
    "endDate": "2024-02-20",
    "endTime": "09:00pm",
    "capacity": 6,
}


def test_builder_post_run(mocker, caplog):
    """Builder notifies the instructor to submi ta log, and the attendee to share feedback"""
    caplog.set_level(logging.INFO)
    got = _mock_builder_singles(
        mocker,
        airtable_fields=TEST_AIRTABLE,
        neon_event=TEST_NEON,
    )
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


def test_builder_far_future(mocker, caplog):
    """Far future classes don't receive any notifications"""
    caplog.set_level(logging.INFO)
    got = _mock_builder_singles(
        mocker,
        airtable_fields=TEST_AIRTABLE,
        neon_event=TEST_NEON,
        now=parse_date("2024-01-01"),
    )
    assert got == []
