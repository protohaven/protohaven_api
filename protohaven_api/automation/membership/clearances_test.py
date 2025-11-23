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


def test_compute_recert_deadline(mocker):
    """Test recertification due date logic"""
    cfg = mocker.Mock(spec=c.airtable.RecertConfig)
    cfg.bypass_cutoff = datetime.timedelta(days=90)
    cfg.bypass_hours = 10

    last_earned = d(0)  # Base date

    # Test 1: Clearance doesn't expire
    cfg.expiration = None
    assert c.compute_recert_deadlines(cfg, last_earned, {}) == (None, None)

    # Test 2: No reservations, just instruction deadline
    cfg.expiration = datetime.timedelta(days=365)
    assert c.compute_recert_deadlines(cfg, last_earned, {}) == (d(365), None)

    # Test 3: Reservations exceeding bypass_hours
    recent_reservations = {d(320): 10, d(350): 6, d(380): 5}
    assert c.compute_recert_deadlines(cfg, last_earned, recent_reservations) == (
        d(365),
        d(350 + 90),
    )

    # Test 4: not enough reservation
    recent_reservations = {d(380): 5}
    assert c.compute_recert_deadlines(cfg, last_earned, recent_reservations) == (
        d(365),
        None,
    )


def test_segment_by_recertification_needed(mocker):
    """Test finding members needing recertification"""
    mocker.patch.object(c, "tznow", return_value=d(0))
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
        contact_info=None,
    )
    needed, not_needed = c.segment_by_recertification_needed(env)

    # Verify results
    assert needed == {(456, "LS1", d(0), None)}
    assert not_needed == {(123, "LS1", d(5), None), (789, "LS1", d(0), d(20))}
    assert not needed.intersection(not_needed)


def test_build_recert_env(mocker):
    """Test building recertification environment with mock data"""
    # Mock the parallel execution components
    mock_recert_configs = {"tool1": {"recert_interval": 365}}
    mock_neon_members = [
        mocker.MagicMock(
            neon_id="123", clearances=["tool1"], emails=["test@example.com"]
        )
    ]
    mock_instructor_clearances = [
        ("test@example.com", ["clearance1"], [], d(1)),  # maps to tool1
        ("test@example.com", [], ["tool1"], d(0)),
    ]
    mock_reservations = {"123": {"tool1": [d(0)]}}
    mocker.patch.object(
        c.airtable, "get_tool_recert_configs_by_code", return_value=mock_recert_configs
    )
    mocker.patch.object(c.neon, "search_all_members", return_value=mock_neon_members)
    mocker.patch.object(
        c.sheets,
        "get_passing_student_clearances",
        return_value=mock_instructor_clearances,
    )
    mocker.patch.object(c, "_structured_reservations", return_value=mock_reservations)
    mocker.patch.object(
        c,
        "resolve_codes",
        side_effect=lambda codes: [{"clearance1": "tool1"}.get(c) for c in codes],
    )

    # Execute the function
    result = c.build_recert_env(d(0), 1300)

    # Verify the result structure
    assert result.recert_configs == mock_recert_configs
    assert result.neon_clearances == {"123": ["tool1"]}
    assert result.last_earned == {("123", "tool1"): d(1)}
    assert result.reservations == mock_reservations
