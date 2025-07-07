"""Test tech automation (e.g. shift forecast generation"""
import pytest

from protohaven_api.automation.techs import techs as t
from protohaven_api.testing import d


@pytest.mark.parametrize(
    "test_date,ovr,want_am",
    [
        (d(0), None, []),  # Holiday
        (d(1), None, ["Default Tech"]),  # Non-holiday, no override
        (d(1), ["Ovr Tech"], ["Ovr Tech"]),  # Non-holiday with override
        (d(0), ["Ovr Tech"], ["Ovr Tech"]),  # Holiday with override
        (d(1), [], []),  # Non-holiday, override to empty
    ],
)
def test_create_calendar_view(mocker, test_date, ovr, want_am):
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
        return_value=("123", [_mock_tech(n) for n in ovr], "Foo")
        if ovr is not None
        else (None, [], None),
    )
    result = t.create_calendar_view(test_date, {shift: [mock_tech]}, ovr, 1)
    assert [p.name for p in result[0]["AM"]["people"]] == want_am


def test_resolve_overrides(mocker):
    """Test resolving tech overrides with various scenarios"""
    # Setup test data
    test_overrides = {
        "shift1": ("id1", ["John Doe", "Jane Smith"], "editor1"),
        "shift2": ("id2", ["Guest Tech"], None),
    }

    # Mock neon.search_members_by_name
    mock_member1 = mocker.MagicMock()
    mock_member2 = mocker.MagicMock()
    mocker.patch.object(
        t.neon,
        "search_members_by_name",
        side_effect=[
            [mock_member1],  # John Doe
            [mock_member2],  # Jane Smith
            [],  # Guest Tech (not found)
        ],
    )

    # Test shift with existing members
    got = t.resolve_overrides(test_overrides, "shift1")
    assert got[0] == "id1"
    assert got[1] == [mock_member1, mock_member2]
    assert got[2] == "editor1"

    # Test shift with guest tech
    got = t.resolve_overrides(test_overrides, "shift2")
    assert got[0] == "id2"
    assert len(got[1]) == 1
    assert got[1][0].name == "Guest Tech"
    assert got[2] is None

    # Test shift not in overrides
    got = t.resolve_overrides(test_overrides, "missing_shift")
    assert got == (None, [], None)
