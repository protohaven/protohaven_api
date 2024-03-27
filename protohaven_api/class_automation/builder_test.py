"""Unit tests for builder module"""
from dateutil.parser import parse as parse_date

from protohaven_api.class_automation import builder
from protohaven_api.class_automation.testdata import assert_matches_testdata


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
