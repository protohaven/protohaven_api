"""Test methods for membership automation commands"""

import datetime

import pytest
from dateutil import parser as dateparser

from protohaven_api.automation.membership import membership as m
from protohaven_api.config import tz
from protohaven_api.integrations import neon  # pylint: disable=import-error
from protohaven_api.testing import d

# pylint: skip-file


@pytest.mark.parametrize(
    "include_filter,initializes",
    [
        (None, True),
        ("j@d.com", True),
        ("a@b.com", False),
        ("None", False),
        ("", True),
    ],
)
def test_init_membership(mocker, include_filter, initializes):
    """Test init_membership"""
    m1 = mocker.patch.object(
        neon, "set_membership_date_range", return_value=mocker.Mock(status_code=200)
    )
    mocker.patch.object(m, "try_cached_coupon", return_value="test_code")
    m2 = mocker.patch.object(
        neon,
        "update_account_automation_run_status",
        return_value=mocker.Mock(status_code=200),
    )
    mocker.patch.object
    mocker.patch.object(
        m,
        "get_sample_classes",
        return_value=[
            {"date": d(0), "name": "class1", "id": 1, "remaining": 2},
            {"date": d(1), "name": "class2", "id": 1, "remaining": 2},
        ],
    )
    mocker.patch.object(m, "get_config", return_value=include_filter)
    # Test with coupon_amount > 0
    msg = m.init_membership("123", "456", "j@d.com", "John Doe", 50, apply=True)
    if initializes:
        assert msg.subject == "John Doe: your first class is on us!"
        assert "class1" in msg.body
        m1.assert_called_with(
            "456",
            m.PLACEHOLDER_START_DATE,
            m.PLACEHOLDER_START_DATE + datetime.timedelta(days=30),
        )
        m2.assert_called_with("123", m.DEFERRED_STATUS)
    else:
        assert msg == None
        m1.assert_not_called()
        m2.assert_not_called()


def test_init_membership_no_classes(mocker):
    """Test init_membership without list of classes"""
    mocker.patch.object(
        neon, "set_membership_date_range", return_value=mocker.Mock(status_code=200)
    )
    mocker.patch.object(m, "try_cached_coupon", return_value="test_code")
    mocker.patch.object(
        neon,
        "update_account_automation_run_status",
        return_value=mocker.Mock(status_code=200),
    )
    mocker.patch.object(m, "get_sample_classes", return_value=[])
    mocker.patch.object(m, "get_config", return_value=None)
    # Test with coupon_amount > 0
    msg = m.init_membership("123", "456", "j@d.com", "John Doe", 50, apply=True)
    assert msg.subject == "John Doe: your first class is on us!"
    assert "Here's a couple basic classes" not in msg.body


def test_event_is_suggestible(mocker):
    """Test that suggestible events are returned if under max price"""
    max_price = 100
    tickets = [
        {"name": "Single Registration", "fee": 50, "numberRemaining": 5},
        {"name": "VIP Registration", "fee": 80, "numberRemaining": 2},
    ]
    mocker.patch.object(neon, "fetch_tickets", return_value=tickets)
    result, number_remaining = m.event_is_suggestible(123, max_price)
    assert result is True
    assert number_remaining == 5


def test_event_is_suggestible_price_too_high(mocker):
    """Test that events aren't returned if they exceed the max_price"""
    max_price = 40
    tickets = [
        {"name": "Single Registration", "fee": 50, "numberRemaining": 3},
    ]
    mocker.patch.object(neon, "fetch_tickets", return_value=tickets)
    result, _ = m.event_is_suggestible(123, max_price)
    assert result is False


def test_generate_coupon_id():
    """Test that coupons are generated uniquely"""
    got = m.generate_coupon_id(n=10)
    assert len(got) == 10
    assert m.generate_coupon_id(n=10) != got


def test_get_sample_classes(mocker):
    """Test fetching of sample classes"""
    mocker.patch.object(
        neon,
        "fetch_upcoming_events",
        return_value=[
            {
                "id": 1,
                "startDate": "2023-10-10",
                "startTime": "10:00AM",
                "name": "Class 1",
            },
            {
                "id": 2,
                "startDate": "2023-10-11",
                "startTime": "11:00AM",
                "name": "Class 2",
            },
            {
                "id": 3,
                "startDate": "2023-10-12",
                "startTime": "12:00PM",
                "name": "Class 3",
            },
        ],
    )
    mocker.patch.object(
        m,
        "event_is_suggestible",
        side_effect=[(True, 5), (True, 1), (False, 0)],
    )
    result = m.get_sample_classes(10)
    assert result == [
        {
            "date": dateparser.parse("2023-10-10T10:00:00").astimezone(tz),
            "name": "Class 1",
            "id": 1,
            "remaining": 5,
        },
        {
            "date": dateparser.parse("2023-10-11T11:00:00").astimezone(tz),
            "name": "Class 2",
            "id": 2,
            "remaining": 1,
        },
    ]


def test_try_cached_coupon_no_coupon(mocker):
    """Test try_cached_coupon when no coupon is available"""
    mocker.patch.object(m.airtable, "get_next_available_coupon", return_value=None)
    mock_send_discord = mocker.patch.object(m.comms, "send_discord_message")
    mock_generate_coupon_id = mocker.patch.object(
        m, "generate_coupon_id", return_value="new_cid"
    )
    mock_create_coupon_code = mocker.patch.object(m.neon, "create_coupon_code")

    result = m.try_cached_coupon(10, "assignee", True)

    mock_send_discord.assert_called_once()
    mock_generate_coupon_id.assert_called_once()
    mock_create_coupon_code.assert_called_once_with("new_cid", 10)
    assert result == "new_cid"


def test_try_cached_coupon_with_coupon_matching(mocker):
    """Test try_cached_coupon with matching coupon available"""
    mocker.patch.object(
        m.airtable,
        "get_next_available_coupon",
        return_value={
            "fields": {"Amount": 10, "Code": "valid_code"},
            "id": "coupon_id",
        },
    )
    mock_mark_coupon_assigned = mocker.patch.object(m.airtable, "mark_coupon_assigned")

    result = m.try_cached_coupon(10, "assignee", True)

    mock_mark_coupon_assigned.assert_called_once_with("coupon_id", "assignee")
    assert result == "valid_code"


def test_try_cached_coupon_with_coupon_mismatch(mocker):
    """Test try_cached_coupon with coupon amount mismatch"""
    mocker.patch.object(
        m.airtable,
        "get_next_available_coupon",
        return_value={
            "fields": {"Amount": 20, "Code": "mismatch_code"},
            "id": "coupon_id",
        },
    )
    mock_send_discord = mocker.patch.object(m.comms, "send_discord_message")
    mock_generate_coupon_id = mocker.patch.object(
        m, "generate_coupon_id", return_value="new_cid"
    )
    mock_create_coupon_code = mocker.patch.object(m.neon, "create_coupon_code")

    result = m.try_cached_coupon(10, "assignee", True)

    mock_send_discord.assert_called_once()
    mock_generate_coupon_id.assert_called_once()
    mock_create_coupon_code.assert_called_once_with("new_cid", 10)
    assert result == "new_cid"
