"""Unit tests for policy enforcement methods"""

from dateutil import parser as dateparser

from protohaven_api.policy_enforcement import enforcer
from protohaven_api.policy_enforcement.testing import *  # pylint: disable=unused-wildcard-import,wildcard-import


def test_gen_fees_closed_violation_subday():
    """If a violation was closed the day it was opened,
    don't add a fee"""
    got = enforcer.gen_fees(
        [violation(1, dt(-2), dt(-2).replace(hour=23, minute=59, second=59))], {}, now
    )
    assert not got


def test_gen_fees_closed_violation_backfills():
    """Fees accumulate on any prior days that have no record"""
    got = enforcer.gen_fees([violation(1, dt(-3), dt(-1))], {}, now)
    assert got == [(1, TESTFEE, Any()), (1, TESTFEE, Any())]


def test_gen_fees_closed_violation_no_action():
    """Violations that are caught up on fees receive no additional fees"""
    got = enforcer.gen_fees([violation(1, dt(-1), None)], {1: now}, now)
    assert not got


def test_gen_fees_new_violation():
    """A new open violation doesn't accumulate fees until a day later"""
    got = enforcer.gen_fees([violation(1, now, None)], {}, now)
    assert not got


def test_gen_fees_applied_by_day():
    """Application boundary for fees is the turnover of the day, not
    actually 24 hours"""
    t1 = dateparser.parse("2024-03-01 12:30pm")
    t2 = dateparser.parse("2024-03-02 7:30am")
    print(t1)
    print(t2)
    print(t2 - t1)
    assert (t2 - t1).days == 0
    got = enforcer.gen_fees([violation(1, t1, None)], {}, t2)
    assert got == [(1, TESTFEE, Any())]


def test_gen_fees_ongoing_violation():
    """An ongoing violation accumulates fees"""
    got = enforcer.gen_fees([violation(1, dt(-2), None)], {1: dt(-1)}, now)
    assert got == [(1, TESTFEE, now.strftime("%Y-%m-%d"))]


def test_gen_fees_ongoing_violation_caught_up():
    """An ongoing violation with a current history of fees is not added to"""
    got = enforcer.gen_fees([violation(1, dt(-2), None)], {1: now}, now)
    assert not got


def test_next_suspension_duration_none():
    """A neon ID with no history receives the base suspension duration"""
    assert (
        enforcer.next_suspension_duration([], now)["12345"]
        == enforcer.SUSPENSION_DAYS_INITIAL
    )


def test_next_suspension_duration_aged_out():
    """A neon ID with a prior suspension past the TTL still receives the
    initial duration"""
    s = suspension(
        dt(-enforcer.SUSPENSION_MAX_AGE_DAYS - 2),
        dt(-enforcer.SUSPENSION_MAX_AGE_DAYS - 1),
    )
    assert (
        enforcer.next_suspension_duration([s], now)["12345"]
        == enforcer.SUSPENSION_DAYS_INITIAL
    )


def test_next_suspension_duration_single():
    """A neon ID with a single past suspension receives an increased suspension
    duration on the second offense"""
    s = suspension(
        dt(-enforcer.SUSPENSION_MAX_AGE_DAYS / 2),
        dt(-enforcer.SUSPENSION_MAX_AGE_DAYS / 2 + 1),
    )
    assert (
        enforcer.next_suspension_duration([s], now)[TESTMEMBER["id"]]
        == enforcer.SUSPENSION_DAYS_INITIAL + enforcer.SUSPENSION_DAYS_INCREMENT
    )


def test_next_suspension_duration_multi():
    """Multiple suspensions within the TTL increase the suspension duration"""
    ss = [
        suspension(
            dt(-enforcer.SUSPENSION_MAX_AGE_DAYS / 2),
            dt(-enforcer.SUSPENSION_MAX_AGE_DAYS / 2 + 1),
        ),
        suspension(
            dt(-enforcer.SUSPENSION_MAX_AGE_DAYS / 3),
            dt(-enforcer.SUSPENSION_MAX_AGE_DAYS / 3 + 1),
        ),
    ]
    assert (
        enforcer.next_suspension_duration(ss, now)[TESTMEMBER["id"]]
        == enforcer.SUSPENSION_DAYS_INITIAL + 2 * enforcer.SUSPENSION_DAYS_INCREMENT
    )


def test_next_suspension_duration_unrelated():
    """Unrelated suspension information does not affect the neon ID's duration"""
    s = suspension(
        dt(-enforcer.SUSPENSION_MAX_AGE_DAYS - 2),
        dt(-enforcer.SUSPENSION_MAX_AGE_DAYS - 1),
    )
    s["fields"]["Neon ID"] = "67890"
    assert (
        enforcer.next_suspension_duration([s], now)["12345"]
        == enforcer.SUSPENSION_DAYS_INITIAL
    )


def test_gen_suspensions_basic():
    """Enough violations before the TTL triggers a suspension"""
    # Three violations on the very edge of enforcement age
    vs = [
        violation(
            i,
            dt(-enforcer.VIOLATION_MAX_AGE_DAYS + 1 + i),
            dt(-enforcer.VIOLATION_MAX_AGE_DAYS + 1 + i),
        )
        for i in range(enforcer.MAX_VIOLATIONS_BEFORE_SUSPENSION)
    ]
    got = enforcer.gen_suspensions(vs, [], now)
    assert got == [("1111", enforcer.SUSPENSION_DAYS_INITIAL, [0, 1, 2])]


def test_gen_suspensions_all_anonymous():
    """Anonymous violations do not create suspensions; there's no one to
    assign the suspension to"""
    vs = [
        violation(i, dt(-2 * i - 1), dt(-2 * i - 1))
        for i in range(enforcer.MAX_VIOLATIONS_BEFORE_SUSPENSION)
    ]
    for v in vs:
        v["fields"]["Neon ID"] = None
    got = enforcer.gen_suspensions(vs, [], now)
    assert not got


def test_gen_suspensions_within_threshold():
    """Fewer violations than the threshold do not trigger a suspension"""
    vs = [
        violation(i, dt(-2 * i - 1), dt(-2 * i - 1))
        for i in range(enforcer.MAX_VIOLATIONS_BEFORE_SUSPENSION - 1)
    ]

    # Include one that's aged out, not counted towards suspension
    vs.append(
        violation(
            999,
            dt(-enforcer.VIOLATION_MAX_AGE_DAYS - 1),
            dt(-enforcer.VIOLATION_MAX_AGE_DAYS - 1),
        )
    )

    got = enforcer.gen_suspensions(vs, [], now)
    assert not got


def test_gen_suspensions_overlapping_violations():
    """Multiple overlapping violations shouldn't trigger suspension"""
    vs = [
        violation(i, dt(-2), dt(-1))
        for i in range(enforcer.MAX_VIOLATIONS_BEFORE_SUSPENSION)
    ]
    got = enforcer.gen_suspensions(vs, [], now)
    assert not got


def test_gen_suspensions_grace_period():
    """Multiple violations shouldn't trigger suspension if there's an open
    one within the grace period"""

    # Enough violations to suspend
    vs = [
        violation(i, dt(-2 * i - 1), dt(-2 * i - 1))
        for i in range(enforcer.MAX_VIOLATIONS_BEFORE_SUSPENSION)
    ]

    # But there's one open and still within grace period
    vs.append(violation(999, dt(-enforcer.OPEN_VIOLATION_GRACE_PD_DAYS + 1), None))

    got = enforcer.gen_suspensions(vs, [], now)
    assert not got


def test_gen_suspensions_unresolved_overlapping():
    """Members can't leave a violation open and have an eternal grace period"""
    # Almost enough very fresh violations
    vs = [
        violation(i, dt(-2 * i - 1), dt(-2 * i - 1))
        for i in range(enforcer.MAX_VIOLATIONS_BEFORE_SUSPENSION - 1)
    ]

    # Plus one that's almost aged out, but still open
    vs.append(violation(999, dt(enforcer.VIOLATION_MAX_AGE_DAYS + 1), None))
    got = enforcer.gen_suspensions(vs, [], now)
    assert got == [("1111", enforcer.SUSPENSION_DAYS_INITIAL, [1, 0, 999])]


def test_gen_suspensions_reset_after_suspended():
    """Carrying out a suspension prevents 'double jeopardy'"""
    # Enough suspensions to violate
    vs = [
        violation(i, dt(-i - 5), dt(-i - 5))
        for i in range(enforcer.MAX_VIOLATIONS_BEFORE_SUSPENSION)
    ]
    assert len(enforcer.gen_suspensions(vs, [], now)) > 0

    # If we've just waited out a suspension period, don't add another suspension
    ss = [suspension(dt(-3), dt(-3))]
    got = enforcer.gen_suspensions(vs, ss, now)
    assert not got

    # But if we start to violate again (even if not resolved)
    # the suspension is reinstated and runs for longer
    vs.append(violation(999, dt(-1), None))
    got = enforcer.gen_suspensions(vs, ss, now)
    assert got == [
        (
            "1111",
            enforcer.SUSPENSION_DAYS_INITIAL + enforcer.SUSPENSION_DAYS_INCREMENT,
            [2, 1, 0, 999],
        )
    ]


def test_gen_comms_for_violation_new():
    """Violation comms render properly for a new violation"""
    v = violation(1, dt(0), None)
    subject, got, _ = enforcer.gen_comms_for_violation(
        v, 0, 0, ["section1", "section2"], TESTMEMBER
    )
    assert "new Protohaven violation issued" in subject
    assert "$5 per day" in got
    assert "testname" in got
    assert dt(0).strftime("%Y-%m-%d") in got
    assert "section1" in got
    assert "section2" in got


def test_gen_comms_for_violation_existing():
    """Violation comms render properly for an ongoing violation"""
    v = violation(1, dt(-1), None)
    subject, got, _ = enforcer.gen_comms_for_violation(
        v, 50, 15, ["section1", "section2"], TESTMEMBER
    )
    assert "ongoing" in subject
    assert "$65" in subject
    assert "$5 per day" in got
    assert "testname" in got
    assert dt(-1).strftime("%Y-%m-%d") in got
    assert "section1" in got
    assert "section2" in got


def test_gen_comms_for_violation_resolved():
    """Resolved violations do not result in comms"""
    v = violation(1, dt(-1), now)
    got = enforcer.gen_comms_for_violation(
        v, 50, 15, ["section1", "section2"], TESTMEMBER
    )
    assert not got


def test_gen_comms_for_violation_incomplete():
    """Violations missing start date aren't given comms"""
    v = violation(1, None, None)
    got = enforcer.gen_comms_for_violation(v, 50, 15, [], TESTMEMBER)
    assert not got


def test_gen_comms_for_violation_unknown_member():
    """If member is unknown, don't generate comms to the violation member"""
    v = violation(1, None, None)
    got = enforcer.gen_comms_for_violation(v, 0, 0, [], None)
    assert not got


def test_gen_comms_for_violation_no_fee():
    """Violations without fees are still sent to the suspect"""
    v = violation(1, dt(-1), None)
    v["fields"]["Daily Fee"] = 0

    subject, got, _ = enforcer.gen_comms_for_violation(
        v, 0, 0, ["section1", "section2"], TESTMEMBER
    )
    assert "violation" in subject
    assert "have accrued" not in got
    assert "testname" in got
    assert dt(-1).strftime("%Y-%m-%d") in got
    assert "section1" in got
    assert "section2" in got


def test_gen_comms_for_suspensions_with_accrued():
    """Suspensions with accrued fees are indicated in comms"""
    s = suspension(
        dt(-1),
        None,
    )
    subject, got, _ = enforcer.gen_comms_for_suspension(s, 100, TESTMEMBER)
    assert "suspended" in subject
    assert "accrued $100" in got
    assert "testname" in got
    assert dt(-1).strftime("%Y-%m-%d") in got


def test_gen_comms_for_suspensions_no_end():
    """Indefinite suspensions are indicated in comms"""
    s = suspension(
        dt(-1),
        None,
    )
    subject, got, _ = enforcer.gen_comms_for_suspension(s, 0, TESTMEMBER)
    assert "suspended" in subject
    assert "accrued" not in got
    assert "testname" in got
    assert dt(-1).strftime("%Y-%m-%d") in got


def test_gen_comms_for_suspension_bounded():
    """Bounded suspensions mention the end date"""
    s = suspension(
        dt(-1),
        dt(4),
    )
    subject, got, _ = enforcer.gen_comms_for_suspension(s, 0, TESTMEMBER)
    assert "suspended" in subject
    assert f"until {dt(4).strftime('%Y-%m-%d')}"
    assert "testname" in got


def test_gen_comms_empty_array_if_nothing_interesting(mocker):
    """Ensure that gen_comms isn't excessively noisy if there's nothing to noise about"""
    mocker.patch.object(enforcer.airtable, "get_policy_sections", return_value=[])
    mocker.patch.object(enforcer.airtable, "get_policy_fees", return_value=[])
    got = enforcer.gen_comms([], [], [], [])
    assert not got
