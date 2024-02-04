"""Tests for communications about policy enforcement"""
from protohaven_api.policy_enforcement import comms
from protohaven_api.policy_enforcement.testing import *  # pylint: disable=unused-wildcard-import,wildcard-import


def test_enforcement_summary_nothing():
    """No data, no summary"""
    got = comms.enforcement_summary([], [], [], [])
    assert not got


def test_enforcement_summary_only_resolved():
    """No summary sent if all items are resolved"""
    got = comms.enforcement_summary(
        [violation(1, dt(-2), dt(-1))],
        [testfee(paid=True), testfee(paid=True)],
        [testfee(paid=True), testfee(paid=True)],
        [suspension(dt(-1), dt(0), reinstated=True)],
    )
    assert not got


def test_enforcement_summary_ignores_complete_but_preserves_fees():
    """Resolved violations and suspensions aren't listed, but any
    unpaid fees from closed violations are mentioned"""
    _, got = comms.enforcement_summary(
        [violation(1, dt(-2)), violation(2, dt(-1), dt(0))],
        [testfee(vid=2), testfee(vid=1, paid=True)],
        [testfee(paid=True), testfee(vid=1)],
        [suspension(dt(-1), dt(0))],
    )
    assert "1 active violation(s)" in got
    assert "1 new suspension(s)" in got
    assert "$5 in unpaid fees" in got


def test_enforcement_summary_unknown_suspect_with_fees():
    """Unknown suspects are summarized, with their accrued fees"""
    _, got = comms.enforcement_summary(
        [violation(1, dt(-1), neon_id=None)],
        [testfee(vid=1, amt=15)],
        [],
        [],
    )
    assert "Suspect: unknown" in got
    assert "Accrued: $15" in got


def test_enforcement_summary_known_suspect_with_fees():
    """Known suspects are summarized, with their accrued fees"""
    _, got = comms.enforcement_summary(
        [violation(1, dt(-1))],
        [testfee(vid=1, amt=15)],
        [],
        [],
    )
    assert "Suspect: known" in got
    assert "Accrued: $15" in got


def test_enforcement_summary_suspension_bounded():
    """Bounded suspensions are summarized and include an end time"""
    _, got = comms.enforcement_summary(
        [],
        [],
        [],
        [suspension(dt(-1), dt(0))],
    )
    assert "1 new suspension(s)" in got
    assert "until " + dt(0).strftime("%Y-%m-%d") in got


def test_enforcement_summary_suspension_indefinite():
    """Indefinite suspensions are summarized"""
    _, got = comms.enforcement_summary(
        [],
        [],
        [],
        [suspension(dt(-1))],
    )
    assert "1 new suspension(s)" in got
    assert "until fees paid" in got
