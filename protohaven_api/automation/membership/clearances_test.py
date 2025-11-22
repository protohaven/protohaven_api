"""Tests for clearance automation"""

import datetime

from protohaven_api.automation.membership import clearances as c
from protohaven_api.testing import d


def test_update_patch(mocker):
    """Test the update function"""
    mocker.patch.object(
        c.neon,
        "fetch_clearance_codes",
        return_value=[
            {"name": "CLEAR1", "code": "C1", "id": 1},
            {"name": "CLEAR2", "code": "C2", "id": 2},
        ],
    )
    mocker.patch.object(
        c.neon,
        "search_members_by_email",
        return_value=[
            mocker.MagicMock(neon_id=123, company_id=456, clearances=["CLEAR1"])
        ],
    )
    mocker.patch.object(
        c.airtable, "get_clearance_to_tool_map", return_value={"MWB": ["ABG", "RBP"]}
    )
    mocker.patch.object(c.neon, "set_clearances", return_value="Success")
    mock_notify = mocker.patch.object(c.mqtt, "notify_clearance")

    assert c.update("a@b.com", "PATCH", ["C2"]) == ["C2"]

    # Note that clearance 1 is still set, since it was set already
    c.neon.set_clearances.assert_called_with(  # pylint: disable=no-member
        123, {2, 1}, is_company=False
    )
    mock_notify.assert_has_calls(
        [
            mocker.call(123, "C2", added=True),
        ],
        any_order=True,
    )


def test_is_recert_due(mocker):
    """Test recertification due date logic"""
    cfg = mocker.Mock(spec=c.airtable.RecertConfig)
    cfg.bypass_cutoff = datetime.timedelta(days=90)
    cfg.bypass_hours = 10

    now = d(400)  # Well past expiration
    last_earned = d(0)  # Base date

    # Test 1: Clearance doesn't expire
    cfg.expiration = None
    assert not c.is_recert_due(cfg, now, last_earned, {})

    # Test 2: Clearance not yet expired
    cfg.expiration = datetime.timedelta(days=365)
    now = d(100)  # Before expiration
    assert not c.is_recert_due(cfg, now, last_earned, {})

    # Test 3: Expired but has sufficient tool usage
    now = d(400)  # After expiration
    recent_reservations = {d(350): 6, d(380): 5}  # Within cutoff  # Within cutoff
    assert not c.is_recert_due(cfg, now, last_earned, recent_reservations)

    # Test 4: Expired and insufficient tool usage
    recent_reservations = {
        d(350): 4,  # Within cutoff but total < bypass_hours
        d(380): 3,  # Within cutoff but total < bypass_hours
    }
    assert c.is_recert_due(cfg, now, last_earned, recent_reservations)

    # Test 5: Expired and no recent reservations
    assert c.is_recert_due(cfg, now, last_earned, {})


def test_find_members_needing_recert():
    """Test finding members needing recertification"""
    env = c.RecertEnv(
        recert_configs={
            "LS1": c.airtable.RecertConfig(
                tool="LS1",
                quiz_url=None,
                bypass_tools=["LS1", "LS2"],
                bypass_hours=2,
                bypass_cutoff=datetime.timedelta(days=30),
                expiration=datetime.timedelta(days=6 * 30),
            )
        },
        neon_clearances={
            123: {"LS1"},
            456: {"LS1"},
            789: {"LS1"},
        },
        last_earned={
            (123, "LS1"): d(-(6 * 30) + 5),  # Not quite time to recertify
            (456, "LS1"): d(-(6 * 30)),  # Just due to recertify
            (789, "LS1"): d(-(6 * 30)),  # Just due to recertify
        },
        reservations={
            (456, "LS2"): [(d(-10), d(-10, 1))],  # Not enough tool time
            (789, "LS2"): [(d(-10), d(-10, 2))],  # Enough time to bypass recert
        },
    )
    needed, not_needed = c.segment_by_recertification_needed(env, deadline=d(1))

    # Verify results
    assert needed == {(456, "LS1")}
    assert not_needed == {(123, "LS1"), (789, "LS1")}
    assert not needed.intersection(not_needed)
