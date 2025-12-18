"""Test methods for membership automation commands"""

import datetime

import pytest

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
    mocker.patch.object(
        m,
        "get_sample_classes",
        return_value=[
            {"date": d(0), "name": "class1", "id": 1, "remaining": 2},
            {"date": d(1), "name": "class2", "id": 1, "remaining": 2},
        ],
    )
    mocker.patch.object(
        m,
        "get_config",
        side_effect={
            "neon/webhooks/new_membership/include_filter": include_filter,
            "neon/webhooks/new_membership/excluded_membership_types": None,
            "neon/webhooks/new_membership/additional_targets": "",
        }.get,
    )
    # Test with coupon_amount > 0
    msgs = m.init_membership(
        "123",
        "General",
        "456",
        "j@d.com",
        "John Doe",
        coupon_amount=50,
        apply=True,
        target="j@d.com",
    )
    if initializes:
        assert len(msgs) == 1
        assert msgs[0].subject == "John Doe: your first class is on us!"
        assert "class1" in msgs[0].body
        assert msgs[0].target == "j@d.com"
        m1.assert_called_with(
            "456",
            m.PLACEHOLDER_START_DATE,
            m.PLACEHOLDER_START_DATE + datetime.timedelta(days=30),
        )
        m2.assert_called_with("123", m.DEFERRED_STATUS)
    else:
        assert not msgs
        m1.assert_not_called()
        m2.assert_not_called()


def test_init_membership_addl_targets(mocker):
    """Test init_membership with an additional email target (for observation)"""
    m1 = mocker.patch.object(
        neon, "set_membership_date_range", return_value=mocker.Mock(status_code=200)
    )
    mocker.patch.object(m, "try_cached_coupon", return_value="test_code")
    m2 = mocker.patch.object(
        neon,
        "update_account_automation_run_status",
        return_value=mocker.Mock(status_code=200),
    )
    mocker.patch.object(m, "get_sample_classes", return_value=[])
    mocker.patch.object(
        m,
        "get_config",
        side_effect={
            "neon/webhooks/new_membership/include_filter": "j@d.com",
            "neon/webhooks/new_membership/excluded_membership_types": None,
            "neon/webhooks/new_membership/additional_targets": "test@example.com",
        }.get,
    )
    # Test with coupon_amount > 0
    msgs = m.init_membership(
        "123",
        "General",
        "456",
        "j@d.com",
        "John Doe",
        coupon_amount=50,
        apply=True,
        target="j@d.com",
    )
    assert len(msgs) == 2
    assert msgs[0].target == "j@d.com"
    assert msgs[1].target == "test@example.com"


def test_init_membership_email_filter(mocker):
    """Test init_membership with include filter"""

    # No match --> no results
    mocker.patch.object(
        m,
        "get_config",
        side_effect={"neon/webhooks/new_membership/include_filter": "another_id"}.get,
    )
    msgs = m.init_membership("123", "General", "456", "j@d.com", "John Doe", apply=True)
    assert not msgs

    # Match --> results
    mocker.patch.object(
        m,
        "get_config",
        side_effect={"neon/webhooks/new_membership/include_filter": "j@d.com"}.get,
    )
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
    msgs = m.init_membership("123", "General", "456", "j@d.com", "John Doe", apply=True)
    assert len(msgs) > 0


def test_init_membership_type_filter(mocker):
    """Test init_membership with include filter"""

    # Match --> no results
    mocker.patch.object(
        m,
        "get_config",
        side_effect={
            "neon/webhooks/new_membership/excluded_membership_types": "General"
        }.get,
    )
    msgs = m.init_membership("123", "General", "456", "j@d.com", "John Doe", apply=True)
    assert not msgs

    # No match --> results
    mocker.patch.object(
        m,
        "get_config",
        side_effect={
            "neon/webhooks/new_membership/excluded_membership_types": "AnotherType"
        }.get,
    )
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
    msgs = m.init_membership("123", "General", "456", "j@d.com", "John Doe", apply=True)
    assert len(msgs) > 0


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
    msgs = m.init_membership(
        "123", "General", "456", "j@d.com", "John Doe", coupon_amount=50, apply=True
    )
    assert len(msgs) == 1
    assert msgs[0].subject == "John Doe: your first class is on us!"
    assert "Here's a couple basic classes" not in msgs[0].body


def test_init_membership_amp(mocker):
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
    msgs = m.init_membership(
        "123",
        "AMP Membership",
        "456",
        "j@d.com",
        "John Doe",
        coupon_amount=50,
        apply=True,
    )
    assert len(msgs) == 2
    assert msgs[1].subject == "John Doe: please verify your income"
    assert "proof of income must be on file" in msgs[1].body


def test_generate_coupon_id():
    """Test that coupons are generated uniquely"""
    got = m.generate_coupon_id(n=10)
    assert len(got) == 10
    assert m.generate_coupon_id(n=10) != got


def test_get_sample_classes(mocker):
    """Test fetching of sample classes"""

    m0 = mocker.MagicMock(
        neon_id=1, start_date=d(0, 10), has_open_seats_below_price=lambda p: 5
    )
    m0.name = "Class 1"
    m1 = mocker.MagicMock(
        neon_id=2, start_date=d(1, 11), has_open_seats_below_price=lambda p: 1
    )
    m1.name = "Class 2"
    m2 = mocker.MagicMock(
        neon_id=3, start_date=d(2, 12), has_open_seats_below_price=lambda p: 0
    )
    m2.name = "Class 3"
    mocker.patch.object(
        m.eauto,
        "fetch_upcoming_events",
        return_value=[m0, m1, m2],
    )
    result = m.get_sample_classes(coupon_amount=10)
    assert result == [
        {
            "date": d(0, 10),
            "name": "Class 1",
            "id": 1,
            "remaining": 5,
        },
        {
            "date": d(1, 11),
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
    mock_create_coupon_codes = mocker.patch.object(m.neon, "create_coupon_codes")

    result = m.try_cached_coupon(10, "assignee", True)

    mock_send_discord.assert_called_once()
    mock_generate_coupon_id.assert_called_once()
    mock_create_coupon_codes.assert_called_once_with(["new_cid"], 10)
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
    mock_create_coupon_codes = mocker.patch.object(m.neon, "create_coupon_codes")

    result = m.try_cached_coupon(10, "assignee", True)

    mock_send_discord.assert_called_once()
    mock_generate_coupon_id.assert_called_once()
    mock_create_coupon_codes.assert_called_once_with(["new_cid"], 10)
    assert result == "new_cid"
