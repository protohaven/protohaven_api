"""Unit tests for policy enforcement methods"""
import datetime

from protohaven_api.policy_enforcement import enforcer


class Any:  # pylint: disable=too-few-public-methods
    """Matches any value - used for placeholder matching in asserts"""

    def __eq__(self, other):
        """Check for equality - always true"""
        return True


TESTFEE = 5


def violation(instance, onset, resolution, fee=TESTFEE):
    """Create test violation"""
    return {
        "id": instance,  # for testing, to simplify. This is actually an airtable id
        "fields": {
            "Instance #": instance,
            "Neon ID": "12345",
            "Onset": onset.isoformat() if onset else None,
            "Resolution": resolution.isoformat() if resolution else None,
            "Daily Fee": fee,
        },
    }


def suspension(start, end):
    """Create test suspension"""
    return {
        "id": "12345",  # For testing, to simplify. Actually an airtable ID
        "fields": {
            "Neon ID": "12345",
            "Start Date": start.isoformat(),
            "End Date": end.isoformat() if end else None,
        },
    }


now = datetime.datetime.now()


def dt(days):
    """Returns a date that is `days` away from now"""
    return now + datetime.timedelta(days=days)


def test_gen_fees_closed_violation_subday():
    """If a violation was closed within 24 hours of when it was opened,
    don't add a fee"""
    got = enforcer.gen_fees(
        [violation(1, dt(-2), dt(-2) + datetime.timedelta(hours=23))], {}, now
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
    """A new open violation doesn't accumulate fees until 24hrs later"""
    got = enforcer.gen_fees([violation(1, now, None)], {}, now)
    assert not got


def test_gen_fees_ongoing_violation():
    """An ongoing violation accumulates fees"""
    got = enforcer.gen_fees([violation(1, dt(-2), None)], {1: dt(-1)}, now)
    assert got == [(1, TESTFEE, now)]


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
        enforcer.next_suspension_duration([s], now)["12345"]
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
        enforcer.next_suspension_duration(ss, now)["12345"]
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
    assert got == [("12345", enforcer.SUSPENSION_DAYS_INITIAL)]


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
    assert got == [("12345", enforcer.SUSPENSION_DAYS_INITIAL)]


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
        ("12345", enforcer.SUSPENSION_DAYS_INITIAL + enforcer.SUSPENSION_DAYS_INCREMENT)
    ]
