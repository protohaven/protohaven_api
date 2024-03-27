"""Unit tests for comms module"""
from dateutil.parser import parse as parse_date

from protohaven_api.class_automation import comms
from protohaven_api.class_automation.testdata import assert_matches_testdata

TEST_CLASS = {
    "instructor_firstname": "Test",
    "name": "Class Name",
    "python_date": parse_date("2024-02-20"),
    "capacity": 6,
    "signups": 4,
}
TEST_ATTENDEE = {"firstName": "Test", "email": "test@attendee.com"}


def test_techs_openings():
    """Test tech openings template rendering"""
    subject, body = comms.techs_openings(
        {
            "events": [
                {
                    "id": 1234,
                    "startDate": "2024-02-02",
                    "startTime": "6:00 PM",
                    "name": "Test Class",
                    "capacity": 6,
                    "signups": 2,
                }
            ]
        }
    )
    assert subject == "New classes for tech backfill"
    assert_matches_testdata(body, "test_tech_openings.txt")


def test_automation_summary():
    """Test automation summary template rendering"""
    subject, body = comms.automation_summary(
        {
            "events": {
                "1234": {
                    "action": ["TEST_ACTION"],
                    "name": "TEST EVENT",
                    "targets": ["T1", "T2"],
                },
            },
        }
    )
    assert subject == "Automation notification summary"
    assert_matches_testdata(body, "test_automation_summary.txt")


def test_instructor_update_calendar():
    """Test instructor calendar reminder template rendering"""
    subject, body = comms.instructor_update_calendar(
        "Test Name", parse_date("2024-02-20"), parse_date("2024-03-30")
    )
    assert subject == "Test: please confirm your teaching availability!"
    assert_matches_testdata(body, "test_instructor_update_calendar.txt")


def test_instructor_check_supplies():
    """Test instructor supply check template rendering"""
    subject, body = comms.instructor_check_supplies(TEST_CLASS)
    assert subject == "Class Name on February 20 - please confirm class supplies"
    assert_matches_testdata(body, "test_instructor_check_supplies.txt")


def test_instructor_low_attendance():
    """Test instructor attendance template rendering"""
    subject, body = comms.instructor_low_attendance(TEST_CLASS)
    assert subject == "Class Name on February 20 - help us find 2 more students!"
    assert_matches_testdata(body, "test_instructor_low_attendance.txt")


def test_registrant_class_confirmed():
    """Test registrant confirmation template rendering"""
    subject, body = comms.registrant_class_confirmed(
        TEST_CLASS, TEST_ATTENDEE, now=parse_date("2024-01-30")
    )
    assert subject == "Your class 'Class Name' is on for February 20!"
    assert_matches_testdata(body, "test_registrant_class_confirmed.txt")


def test_instructor_class_confirmed():
    """Test instructor confirmation template rendering"""
    subject, body = comms.instructor_class_confirmed(TEST_CLASS)
    assert subject == "Class Name is on for February 20!"
    assert_matches_testdata(body, "test_instructor_class_confirmed.txt")


def test_registrant_class_cancelled():
    """Test registrant class cancellation rendering"""
    subject, body = comms.registrant_class_cancelled(TEST_CLASS, TEST_ATTENDEE)
    assert subject == "Your class 'Class Name' was cancelled"
    assert_matches_testdata(body, "test_registrant_class_cancelled.txt")


def test_instructor_class_cancelled():
    """Test instructor class cancellation rendering"""
    subject, body = comms.instructor_class_cancelled(TEST_CLASS)
    assert subject == "Your class 'Class Name' was cancelled"
    assert_matches_testdata(body, "test_instructor_class_cancelled.txt")


def test_registrant_post_class_survey():
    """Test reigstrant clsas survey rendering"""
    subject, body = comms.registrant_post_class_survey(TEST_CLASS, TEST_ATTENDEE)
    assert subject == "Class Name: Please share feedback"
    assert_matches_testdata(body, "test_registrant_post_class_survey.txt")


def test_instructor_log_reminder():
    """Test instructor log reminder rendering"""
    subject, body = comms.instructor_log_reminder(TEST_CLASS)
    assert subject == "Class Name: Please submit instructor log"
    assert_matches_testdata(body, "test_instructor_log_reminder.txt")
