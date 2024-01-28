import datetime

from protohaven_api.policy_enforcement import enforcer


class Any:
    def __eq__(self, other):
        return True


TESTFEE = 5


def violation(instance, onset, resolution, fee=TESTFEE):
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


now = datetime.datetime.now()


def dt(days):
    return now + datetime.timedelta(days=days)


def test_gen_fees_closed_violation_subday():
    got = enforcer.gen_fees([violation(1, dt(-2), dt(-2))], {}, now)
    assert got == []


def test_gen_fees_closed_violation_backfills():
    got = enforcer.gen_fees([violation(1, dt(-3), dt(-1))], {}, now)
    assert got == [(1, TESTFEE, Any()), (1, TESTFEE, Any())]


def test_gen_fees_closed_violation_no_action():
    # Violations that are caught up on fees receive no additional fees
    got = enforcer.gen_fees([violation(1, dt(-1), None)], {1: now}, now)
    assert got == []


def test_gen_fees_new_violation():
    got = enforcer.gen_fees([violation(1, now, None)], {}, now)
    assert got == []


def test_gen_fees_ongoing_violation():
    got = enforcer.gen_fees([violation(1, dt(-2), None)], {1: dt(-1)}, now)
    assert got == [(1, TESTFEE, now)]


def test_gen_fees_ongoing_violation_caught_up():
    got = enforcer.gen_fees([violation(1, dt(-2), None)], {1: now}, now)
    assert got == []


def test_next_suspension_duration_none():
    assert (
        enforcer.next_suspension_duration([], now)["12345"]
        == enforcer.INITIAL_SUSPENSION_DAYS
    )


def test_gen_suspensions_basic():
    vs = [
        violation(1, dt(-60), dt(-60)),
        violation(1, dt(-50), dt(-50)),
        violation(1, dt(-40), dt(-40)),
    ]
    got = enforcer.gen_suspensions(vs, {}, now)
    # TODO assert got ==


def test_gen_suspensions_all_anonymous():
    pass


def test_gen_suspensions_within_threshold():
    pass


def test_gen_suspensions_overlapping_violations():
    """3 overlapping violations shouldn't trigger suspension"""
    pass


def test_gen_suspensions_unresolved_overlapping():
    """Members can't leave a violation open and have an eternal grace period"""
    pass
