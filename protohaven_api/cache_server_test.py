"""Tests for the standalone cache server."""

# pylint: skip-file
import json

import pytest

from protohaven_api import cache_server


@pytest.fixture(name="client")
def fixture_client(mocker):
    """Create a test client that mocks out neon.cache and connector init."""
    mocker.patch.object(cache_server, "init_connector")
    mocker.patch.object(cache_server.neon.cache, "start")

    fapp = cache_server.create_app()
    return fapp.test_client()


def _mock_member(mocker, neon_id="123", fname="Alice", lname="Anderson",
                 email="alice@example.com", name="Alice Anderson",
                 status="Active", level="General Membership"):
    """Create a mock Member with the given properties."""
    m = mocker.MagicMock()
    m.neon_id = neon_id
    m.fname = fname
    m.lname = lname
    m.email = email
    m.name = name
    m.account_current_membership_status = status
    m.membership_level = level
    m.neon_search_data = {
        "Account ID": neon_id,
        "First Name": fname,
        "Last Name": lname,
        "Email 1": email,
        "Account Current Membership Status": status,
        "Membership Level": level,
    }
    return m


def test_find_best_match_no_search_param(client):
    """find_best_match returns 400 when search is missing."""
    resp = client.get("/find_best_match")
    assert resp.status_code == 400
    assert json.loads(resp.data) == {"error": "search parameter is required"}


def test_find_best_match_returns_serialized_members(mocker, client):
    """find_best_match calls neon.cache.find_best_match and serializes results."""
    member = _mock_member(mocker)
    mocker.patch.object(
        cache_server.neon.cache,
        "find_best_match",
        return_value=[member],
    )

    resp = client.get("/find_best_match?search=Alice")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert len(data) == 1
    assert data[0]["neon_id"] == "123"
    assert data[0]["fname"] == "Alice"
    assert data[0]["email"] == "alice@example.com"
    assert data[0]["account_current_membership_status"] == "Active"


def test_find_best_match_passes_params(mocker, client):
    """find_best_match passes top_n and score_cutoff through to cache."""
    mocker.patch.object(
        cache_server.neon.cache,
        "find_best_match",
        return_value=[],
    )

    client.get("/find_best_match?search=Bob&top_n=5&score_cutoff=80")
    cache_server.neon.cache.find_best_match.assert_called_with(
        "Bob", top_n=5, score_cutoff=80
    )


def test_get_no_key_param(client):
    """get returns 400 when key is missing."""
    resp = client.get("/get")
    assert resp.status_code == 400
    assert json.loads(resp.data) == {"error": "key parameter is required"}


def test_get_returns_serialized_members(mocker, client):
    """get calls neon.cache.get and serializes result dict."""
    member = _mock_member(mocker)
    mocker.patch.object(
        cache_server.neon.cache,
        "get",
        return_value={"123": member},
    )

    resp = client.get("/get?key=alice@example.com")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "123" in data
    assert data["123"]["neon_id"] == "123"
    assert data["123"]["email"] == "alice@example.com"


def test_get_empty_result(mocker, client):
    """get returns empty dict when cache returns nothing."""
    mocker.patch.object(
        cache_server.neon.cache,
        "get",
        return_value={},
    )

    resp = client.get("/get?key=nonexistent@example.com")
    assert resp.status_code == 200
    assert json.loads(resp.data) == {}


def test_serialize_member(mocker):
    """_serialize_member extracts the right fields from a Member."""
    member = _mock_member(
        mocker,
        neon_id="456",
        fname="Bob",
        lname="Builder",
        email="bob@example.com",
        name="Bob Builder",
        status="Future",
        level="Weekend Membership",
    )
    result = cache_server._serialize_member(member)
    assert result == {
        "neon_id": "456",
        "fname": "Bob",
        "lname": "Builder",
        "email": "bob@example.com",
        "name": "Bob Builder",
        "account_current_membership_status": "Future",
        "membership_level": "Weekend Membership",
        "neon_search_data": member.neon_search_data,
    }
