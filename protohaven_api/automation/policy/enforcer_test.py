"""Unit tests for policy enforcement methods"""

from protohaven_api.automation.policy import enforcer
from protohaven_api.config import safe_parse_datetime
from protohaven_api.automation.policy.testing import (
    TESTFEE,
    TESTMEMBER,
    dt,
    now,
    violation,
)


def test_gen_fees_closed_violation_subday():
    """If a violation was closed the day it was opened,
    don't add a fee"""
    got = enforcer.gen_fees(
        [violation(1, dt(-2), dt(-2).replace(hour=23, minute=59, second=59))], {}, now
    )
    assert not got


def test_gen_fees_closed_violation_backfills(mocker):
    """Fees accumulate on any prior days that have no record"""
    got = enforcer.gen_fees([violation(1, dt(-3), dt(-1))], {}, now)
    assert got == [(1, TESTFEE, mocker.ANY), (1, TESTFEE, mocker.ANY)]


def test_gen_fees_closed_violation_no_action():
    """Violations that are caught up on fees receive no additional fees"""
    got = enforcer.gen_fees([violation(1, dt(-1), None)], {1: now}, now)
    assert not got


def test_gen_fees_new_violation():
    """A new open violation doesn't accumulate fees until a day later"""
    got = enforcer.gen_fees([violation(1, now, None)], {}, now)
    assert not got


def test_gen_fees_applied_by_day(mocker):
    """Application boundary for fees is the turnover of the day, not
    actually 24 hours"""
    t1 = safe_parse_datetime("2024-03-01 12:30pm")
    t2 = safe_parse_datetime("2024-03-02 7:30am")
    print(t1)
    print(t2)
    print(t2 - t1)
    assert (t2 - t1).days == 0
    got = enforcer.gen_fees([violation(1, t1, None)], {}, t2)
    assert got == [(1, TESTFEE, mocker.ANY)]


def test_gen_fees_ongoing_violation():
    """An ongoing violation accumulates fees"""
    got = enforcer.gen_fees([violation(1, dt(-2), None)], {1: dt(-1)}, now)
    assert got == [(1, TESTFEE, now.strftime("%Y-%m-%d"))]


def test_gen_fees_ongoing_violation_caught_up():
    """An ongoing violation with a current history of fees is not added to"""
    got = enforcer.gen_fees([violation(1, dt(-2), None)], {1: now}, now)
    assert not got


def test_gen_comms_for_violation_new():
    """Violation comms render properly for a new violation"""
    v = violation(1, dt(0), None)
    msg = enforcer.gen_comms_for_violation(
        v, 0, 0, ["section1", "section2"], TESTMEMBER["firstName"], TESTMEMBER["email1"]
    )
    assert "new Protohaven violation issued" in msg.subject
    assert "$5 per day" in msg.body
    assert "testname" in msg.body
    assert dt(0).strftime("%Y-%m-%d") in msg.body
    assert "section1" in msg.body
    assert "section2" in msg.body


def test_gen_comms_for_violation_existing():
    """Violation comms render properly for an ongoing violation"""
    v = violation(1, dt(-1), None)
    msg = enforcer.gen_comms_for_violation(
        v,
        50,
        15,
        ["section1", "section2"],
        TESTMEMBER["firstName"],
        TESTMEMBER["email1"],
    )
    assert "ongoing" in msg.subject
    assert "$65" in msg.subject
    assert "$5 per day" in msg.body
    assert "testname" in msg.body
    assert dt(-1).strftime("%Y-%m-%d") in msg.body
    assert "section1" in msg.body
    assert "section2" in msg.body


def test_gen_comms_for_violation_resolved():
    """Resolved violations do not result in comms"""
    v = violation(1, dt(-1), now)
    got = enforcer.gen_comms_for_violation(
        v,
        50,
        15,
        ["section1", "section2"],
        TESTMEMBER["firstName"],
        TESTMEMBER["email1"],
    )
    assert not got


def test_gen_comms_for_violation_incomplete():
    """Violations missing start date aren't given comms"""
    v = violation(1, None, None)
    got = enforcer.gen_comms_for_violation(
        v, 50, 15, [], TESTMEMBER["firstName"], TESTMEMBER["email1"]
    )
    assert not got


def test_gen_comms_for_violation_unknown_member():
    """If member is unknown, don't generate comms to the violation member"""
    v = violation(1, None, None)
    got = enforcer.gen_comms_for_violation(v, 0, 0, [], None, None)
    assert not got


def test_gen_comms_for_violation_no_fee():
    """Violations without fees are still sent to the suspect"""
    v = violation(1, dt(-1), None)
    v["fields"]["Daily Fee"] = 0

    msg = enforcer.gen_comms_for_violation(
        v, 0, 0, ["section1", "section2"], TESTMEMBER["firstName"], TESTMEMBER["email1"]
    )
    assert "violation" in msg.subject
    assert "have accrued" not in msg.body
    assert "testname" in msg.body
    assert dt(-1).strftime("%Y-%m-%d") in msg.body
    assert "section1" in msg.body
    assert "section2" in msg.body


def test_gen_comms_empty_array_if_nothing_interesting(mocker):
    """Ensure that gen_comms isn't excessively noisy if there's nothing to noise about"""
    mocker.patch.object(enforcer.airtable, "get_policy_sections", return_value=[])
    mocker.patch.object(enforcer.airtable, "get_policy_fees", return_value=[])
    got = enforcer.gen_comms([], [], [])
    assert not got
