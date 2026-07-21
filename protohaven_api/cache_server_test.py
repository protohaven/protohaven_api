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


def _mock_member(
    mocker,
    neon_id="123",
    fname="Alice",
    lname="Anderson",
    email="alice@example.com",
    name="Alice Anderson",
    status="Active",
    level="General Membership",
):
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
    m.neon_raw_data = {}
    m.neon_membership_data = None
    m.airtable_bio_data = {}
    return m


def _expected_serialized(member):
    """Build expected dict that asdict would produce from a mock Member.

    Since mock objects don't work with dataclasses.asdict, we define the
    expected output manually to match the Member dataclass fields.
    """
    return {
        "neon_raw_data": member.neon_raw_data,
        "neon_search_data": member.neon_search_data,
        "neon_membership_data": member.neon_membership_data,
        "airtable_bio_data": member.airtable_bio_data,
    }


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
    assert data[0] == _expected_serialized(member)


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
    assert data["123"] == _expected_serialized(member)


def test_neon_id_from_booked_id_no_param(client):
    """neon_id_from_booked_id returns 400 when booked_id is missing."""
    resp = client.get("/neon_id_from_booked_id")
    assert resp.status_code == 400
    assert json.loads(resp.data) == {"error": "booked_id parameter is required"}


def test_neon_id_from_booked_id_invalid_param(client):
    """neon_id_from_booked_id returns 400 when booked_id is not an integer."""
    resp = client.get("/neon_id_from_booked_id?booked_id=abc")
    assert resp.status_code == 400
    assert json.loads(resp.data) == {"error": "booked_id must be an integer"}


def test_neon_id_from_booked_id_returns_neon_id(mocker, client):
    """neon_id_from_booked_id calls cache and returns the neon_id."""
    mocker.patch.object(
        cache_server.neon.cache,
        "neon_id_from_booked_id",
        return_value="456",
    )

    resp = client.get("/neon_id_from_booked_id?booked_id=42")
    assert resp.status_code == 200
    assert json.loads(resp.data) == {"neon_id": "456"}
    cache_server.neon.cache.neon_id_from_booked_id.assert_called_with(42)


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


def test_neon_ratelimit_ok(mocker, client):
    """neon_ratelimit_ok acquires the lock, sleeps, and returns 200 OK."""
    # Mock the lock and sleep to verify behavior without actually blocking
    mock_lock = mocker.MagicMock()
    mocker.patch.object(cache_server, "neon_ratelimit", mock_lock)
    mocker.patch.object(cache_server.time, "sleep")

    resp = client.get("/neon_ratelimit_ok")
    assert resp.status_code == 200
    assert json.loads(resp.data) == {"ok": True}
    # Verify lock was used as a context manager
    mock_lock.__enter__.assert_called_once()
    mock_lock.__exit__.assert_called_once()
    cache_server.time.sleep.assert_called_once()
