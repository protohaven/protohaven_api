"""Test tech automation (e.g. shift forecast generation"""

import unittest.mock

import pytest

from protohaven_api.automation.techs import techs as t
from protohaven_api.testing import d


def test_holiday_customization():
    """Basic check to ensure holiday calendar is working"""
    got = set(t.ProtohavenHolidays(years=2025).values())
    assert {
        "New Year's Eve",
        "New Year's Day",
        "Martin Luther King Day",
        "Easter Sunday",
        "Memorial Day",
        "Juneteenth",
        "Independence Day",
        "Labor Day",
        "Thanksgiving Day",
        "Day After Thanksgiving",
        "Christmas Eve",
        "Christmas Day",
    } == got
    # Monday is 0, Sunday is 6 in Python's weekday()
    assert t.ProtohavenHolidays(years=2025).get_named("Easter Sunday")[0].weekday() == 6


@pytest.mark.parametrize(
    "test_date,ovr,want_am,is_holiday",
    [
        (d(0), None, [], True),  # Holiday
        (d(1), None, ["Default Tech"], False),  # Non-holiday, no override
        (d(1), ["Ovr Tech"], ["Ovr Tech"], False),  # Non-holiday with override
        (d(0), ["Ovr Tech"], ["Ovr Tech"], True),  # Holiday with override
        (d(1), [], [], False),  # Non-holiday, override to empty
    ],
)
def test_create_calendar_view(mocker, test_date, ovr, want_am, is_holiday):
    """Test generate produces correct output structure"""
    shift = (test_date.strftime("%A"), "AM")

    def _mock_tech(name):
        m = mocker.MagicMock()
        m.name = name
        m.shop_tech_shift = shift
        m.shop_tech_first_day = None
        m.shop_tech_last_day = None
        return m

    mock_tech = _mock_tech("Default Tech")

    mocker.patch.object(
        t,
        "resolve_overrides",
        return_value=(
            ("123", [_mock_tech(n) for n in ovr], "Foo")
            if ovr is not None
            else (None, [], None)
        ),
    )
    result = t.create_calendar_view(test_date, {shift: [mock_tech]}, ovr, 1)
    assert [p.name for p in result[0]["AM"]["people"]] == want_am
    assert result[0]["is_holiday"] == is_holiday


def _mock_tech(name):
    """Helper to create a mock Member with a name"""
    m = unittest.mock.MagicMock()
    m.name = name
    return m


def test_resolve_overrides_legacy_format(mocker):
    """Test resolving tech overrides with legacy (absolute) format"""
    test_overrides = {
        "shift1": ("id1", ["John Doe", "Jane   smith (they/them)"], "editor1"),
        "shift2": ("id2", ["GuestTech"], None),
    }
    shift_people = []  # Not used in legacy mode

    # Mock neon.find_best_match
    mock_member1 = _mock_tech("John Doe")
    mock_member2 = _mock_tech("Jane Smith")
    mocker.patch.object(
        t.neon.cache,
        "find_best_match",
        side_effect=[
            [mock_member1],  # John Doe
            [mock_member2],  # Jane Smith
            [],  # Guest Tech (not found)
        ],
    )

    # Test shift with existing members (legacy absolute format)
    got = t.resolve_overrides(test_overrides, "shift1", shift_people)
    assert got[0] == "id1"
    assert got[1] == [mock_member1, mock_member2]
    assert got[2] == "editor1"

    # Test shift with guest tech
    got = t.resolve_overrides(test_overrides, "shift2", shift_people)
    assert got[0] == "id2"
    assert len(got[1]) == 1
    assert got[1][0].name == "GuestTech"
    assert got[2] is None

    # Test shift not in overrides
    got = t.resolve_overrides(test_overrides, "missing_shift", shift_people)
    assert got == (None, [], None)


def test_resolve_overrides_delta_format_add(mocker):
    """Test delta format: adding a tech to a shift"""
    default_tech = _mock_tech("Default Tech")
    new_tech = _mock_tech("New Tech")

    test_overrides = {
        "shift1": ("id1", ["+New Tech"], "editor1"),
    }
    shift_people = [default_tech]

    mocker.patch.object(
        t.neon.cache,
        "find_best_match",
        side_effect=[
            [new_tech],  # New Tech found
        ],
    )

    got = t.resolve_overrides(test_overrides, "shift1", shift_people)
    assert got[0] == "id1"
    assert got[2] == "editor1"
    # Should contain both the default tech and the added tech
    assert len(got[1]) == 2
    names = {p.name for p in got[1]}
    assert names == {"Default Tech", "New Tech"}


def test_resolve_overrides_delta_format_remove():
    """Test delta format: removing a tech from a shift"""
    default_tech = _mock_tech("Default Tech")
    removed_tech = _mock_tech("Removed Tech")

    test_overrides = {
        "shift1": ("id1", ["-Removed Tech"], "editor1"),
    }
    shift_people = [default_tech, removed_tech]

    # No neon lookup needed for removal (matched by name)
    got = t.resolve_overrides(test_overrides, "shift1", shift_people)
    assert got[0] == "id1"
    assert got[2] == "editor1"
    assert got[1] == [default_tech]


def test_resolve_overrides_delta_format_add_and_remove(mocker):
    """Test delta format: simultaneously adding and removing techs"""
    default_tech = _mock_tech("Default Tech")
    removed_tech = _mock_tech("Removed Tech")
    new_tech = _mock_tech("New Tech")

    test_overrides = {
        "shift1": ("id1", ["+New Tech", "-Removed Tech"], "editor1"),
    }
    shift_people = [default_tech, removed_tech]

    mocker.patch.object(
        t.neon.cache,
        "find_best_match",
        side_effect=[
            [new_tech],
        ],
    )

    got = t.resolve_overrides(test_overrides, "shift1", shift_people)
    assert got[0] == "id1"
    assert got[2] == "editor1"
    assert len(got[1]) == 2
    names = {p.name for p in got[1]}
    assert names == {"Default Tech", "New Tech"}


def test_resolve_overrides_delta_format_guest_tech(mocker):
    """Test delta format: adding a guest tech not found in Neon"""
    default_tech = _mock_tech("Default Tech")

    test_overrides = {
        "shift1": ("id1", ["+Guest Tech"], "editor1"),
    }
    shift_people = [default_tech]

    mocker.patch.object(
        t.neon.cache,
        "find_best_match",
        side_effect=[
            [],  # Guest Tech not found
        ],
    )

    got = t.resolve_overrides(test_overrides, "shift1", shift_people)
    assert got[0] == "id1"
    assert got[2] == "editor1"
    assert len(got[1]) == 2
    names = {p.name for p in got[1]}
    assert names == {"Default Tech", "Guest Tech"}


def test_resolve_overrides_delta_format_new_tech_appears(mocker):
    """Test that a newly enrolled tech with matching default shift appears
    even when an override exists (the core bug fix)."""
    # Scenario: override removes "Old Tech" and adds "Special Tech"
    # A new tech "New Enrollee" has the same default shift
    # They should appear in the final list because the override is a delta,
    # not an absolute list

    old_tech = _mock_tech("Old Tech")
    new_enrollee = _mock_tech("New Enrollee")
    special_tech = _mock_tech("Special Tech")

    test_overrides = {
        "shift1": ("id1", ["+Special Tech", "-Old Tech"], "editor1"),
    }
    shift_people = [old_tech, new_enrollee]

    mocker.patch.object(
        t.neon.cache,
        "find_best_match",
        side_effect=[
            [special_tech],  # Special Tech found
        ],
    )

    got = t.resolve_overrides(test_overrides, "shift1", shift_people)
    assert got[0] == "id1"
    # New Enrollee should be present (came from default shift)
    # Special Tech should be present (added by override)
    # Old Tech should be absent (removed by override)
    names = {p.name for p in got[1]}
    assert names == {"New Enrollee", "Special Tech"}


def test_is_delta_format_detection(mocker):
    """Test detection of delta vs legacy format via resolve_overrides.

    Delta format entries (prefixed with +/-) apply on top of shift_people.
    Legacy format entries (no prefix) replace shift_people entirely."""
    default_tech = _mock_tech("Default Tech")

    # Delta format: adds on top of shift_people
    mocker.patch.object(
        t.neon.cache, "find_best_match", side_effect=[[_mock_tech("New")]]
    )
    got = t.resolve_overrides({"s": ("id", ["+New"], "ed")}, "s", [default_tech])
    assert len(got[1]) == 2  # Default Tech + New

    # Legacy format: replaces shift_people entirely
    mocker.patch.object(
        t.neon.cache, "find_best_match", side_effect=[[_mock_tech("New")]]
    )
    got = t.resolve_overrides({"s": ("id", ["New"], "ed")}, "s", [default_tech])
    assert len(got[1]) == 1  # Only New, Default Tech replaced
    assert got[1][0].name == "New"

    # Empty entries: no override
    got = t.resolve_overrides({"s": ("id", [], "ed")}, "s", [default_tech])
    assert got == (None, [], None)
