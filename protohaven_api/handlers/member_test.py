"""Tests for member handlers"""

import pytest

from protohaven_api.handlers import member
from protohaven_api.integrations import eventbrite, neon
from protohaven_api.testing import (  # pylint: disable=unused-import
    d,
    fixture_client,
    setup_session,
)


@pytest.fixture(name="memclient")
def member_client(client):
    """Mock client with logged in session"""
    setup_session(client, roles=None)
    return client


def test_get_recert_data_not_enabled(mocker, memclient):
    """Test recert endpoint returns 503 when recert not enabled"""
    mocker.patch.object(member, "_fetch_neon_id", return_value="12345")
    mocker.patch.object(member, "_recert_enabled", return_value=False)

    response = memclient.get("/member/recert_data")

    assert response.status_code == 503
    assert response.data.decode() == "Not yet enabled"


def test_get_recert_data_success(mocker, memclient):
    """Test successful recert data retrieval"""
    neon_id = "test_neon_id"
    mock_configs = {
        "LTH": mocker.Mock(
            as_dict=mocker.Mock(
                return_value={"tool": "LTH", "name": "LTH: Metal Lathe"}
            )
        ),
        "MLL": mocker.Mock(
            as_dict=mocker.Mock(
                return_value={"tool": "MLL", "name": "MLL: Manual Mill"}
            )
        ),
    }

    pending_data = [
        (neon_id, "LTH", d(10), d(15), {}),
        ("other_id", "MLL", d(5), d(8), {}),  # Should be filtered out
        (neon_id, "MLL", d(20), d(18), {}),
    ]

    mocker.patch.object(member, "_fetch_neon_id", return_value=neon_id)
    mocker.patch.object(member, "_recert_enabled", return_value=True)
    mocker.patch.object(
        member.airtable, "get_tool_recert_configs_by_code", return_value=mock_configs
    )
    mocker.patch.object(
        member.airtable, "get_pending_recertifications", return_value=pending_data
    )

    response = memclient.get("/member/recert_data")

    assert response.status_code == 200
    data = response.json

    # Check pending items are filtered and sorted
    assert len(data["pending"]) == 2
    assert data["pending"][0][0] == "LTH"
    assert data["pending"][1][0] == "MLL"
    assert data["pending"][0][1] == "2025-01-16"  # max(d(10), d(15))
    assert data["pending"][1][1] == "2025-01-21"  # max(d(20), d(18))

    # Check configs are sorted
    assert len(data["configs"]) == 2
    assert data["configs"][0]["tool"] == "LTH"
    assert data["configs"][1]["tool"] == "MLL"


def test_get_recert_data_no_config_for_tool(mocker, memclient):
    """Test pending recertifications without config are filtered out"""
    neon_id = "test_neon_id"
    mock_configs = {
        "LTH": mocker.Mock(as_dict=mocker.Mock(return_value={"tool": "LTH"}))
    }

    pending_data = [
        (neon_id, "LTH", d(10), d(15), {}),
        (neon_id, "UNKNOWN_TOOL", d(5), d(8), {}),  # No config, should be filtered
    ]

    mocker.patch.object(member, "_fetch_neon_id", return_value=neon_id)
    mocker.patch.object(member, "_recert_enabled", return_value=True)
    mocker.patch.object(
        member.airtable, "get_tool_recert_configs_by_code", return_value=mock_configs
    )
    mocker.patch.object(
        member.airtable, "get_pending_recertifications", return_value=pending_data
    )

    response = memclient.get("/member/recert_data")

    assert response.status_code == 200
    data = response.json
    assert len(data["pending"]) == 1
    assert data["pending"][0][0] == "LTH"


def test_goto_class_non_eventbrite_url(mocker, memclient):
    """Redirects directly for non-Eventbrite URLs"""
    mocker.patch.object(neon, "search_member_by_neon_id")
    mocker.patch.object(eventbrite, "is_valid_id")
    url = "https://example.com/class"
    response = memclient.get(f"/member/goto_class?url={url}")
    assert response.status_code == 302
    assert response.location == url


def test_goto_class_invalid_eventbrite_id(mocker, memclient):
    """Redirects directly when Eventbrite ID is invalid"""
    mocker.patch.object(eventbrite, "is_valid_id", return_value=False)
    url = "https://www.eventbrite.com/e/123456789"
    response = memclient.get(f"/member/goto_class?url={url}")
    assert response.status_code == 302
    assert response.location == url


def test_goto_class_member_not_found(mocker, memclient):
    """Returns 400 when member not found in Neon"""
    mocker.patch.object(eventbrite, "is_valid_id", return_value=True)
    mocker.patch.object(neon, "search_member_by_neon_id", return_value=None)
    mocker.patch.object(member, "_fetch_neon_id", return_value="12345")
    url = "https://www.eventbrite.com/e/123456789"
    response = memclient.get(f"/member/goto_class?url={url}")
    assert response.status_code == 400
    assert "not found" in response.get_data(as_text=True)


def test_goto_class_no_discount_eligible(mocker, memclient):
    """Redirects without discount code when member has 0% discount"""
    mocker.patch.object(eventbrite, "is_valid_id", return_value=True)
    mock_member = mocker.MagicMock()
    mock_member.event_discount_pct.return_value = 0
    mocker.patch.object(neon, "search_member_by_neon_id", return_value=mock_member)
    mocker.patch.object(member, "_fetch_neon_id", return_value="12345")
    url = "https://www.eventbrite.com/e/123456789"
    response = memclient.get(f"/member/goto_class?url={url}")
    assert response.status_code == 302
    assert response.location == "https://www.eventbrite.com/e/123456789/"


def test_goto_class_with_discount(mocker, memclient):
    """Redirects with discount code when member has positive discount"""
    mocker.patch.object(eventbrite, "is_valid_id", return_value=True)
    mock_member = mocker.MagicMock()
    mock_member.event_discount_pct.return_value = 25
    mocker.patch.object(neon, "search_member_by_neon_id", return_value=mock_member)
    mocker.patch.object(member, "_fetch_neon_id", return_value="12345")
    mocker.patch.object(
        eventbrite,
        "generate_discount_code",
        return_value="DISCOUNT25",
    )
    url = "https://www.eventbrite.com/e/123456789"
    response = memclient.get(f"/member/goto_class?url={url}")
    assert response.status_code == 302
    expected_url = "https://www.eventbrite.com/e/123456789/?discount=DISCOUNT25"
    assert response.location == expected_url
