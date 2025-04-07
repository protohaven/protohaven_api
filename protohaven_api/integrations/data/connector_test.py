"""Tests for data connector"""
import json

import pytest

from protohaven_api.integrations.data import connector as con


@pytest.fixture(name="c")
def fixture_connector(mocker):
    """Provide connector fixture"""
    mocker.patch.object(con.requests, "request")
    mocker.patch.object(con, "asana")
    mocker.patch.object(con, "SquareClient")
    mocker.patch.object(con, "discord_bot")
    mocker.patch.object(con.time, "sleep")
    return con.Connector()


def test_airtable_read_retry(mocker, c):
    """ReadTimeout triggers a retry on get requests to Airtable"""
    con.requests.request.side_effect = [
        con.requests.exceptions.ReadTimeout("Whoopsie"),
        mocker.MagicMock(status_code=200, content=json.dumps(True)),
    ]
    status, content = c.db_request("GET", "tools_and_equipment", "tools")
    assert status == 200
    assert content is True
    con.time.sleep.assert_called()


def test_airtable_read_max_retries(c):
    """Too many retries eventually causes a failure"""
    con.requests.request.side_effect = [
        con.requests.exceptions.ReadTimeout("Whoopsie"),
        con.requests.exceptions.ReadTimeout("Whoopsie again"),
        con.requests.exceptions.ReadTimeout("Last Fail"),
    ]
    with pytest.raises(con.requests.exceptions.ReadTimeout):
        c.db_request("GET", "tools_and_equipment", "tools")


def test_neon_request_attendees_endpoint(mocker, c):
    """Ensure /attendees is ratelimited"""
    con.requests.request.return_value = mocker.Mock(
        status_code=200, json=lambda: {"key": "value"}
    )
    assert c.neon_request("api_key", "/attendees") == {"key": "value"}
    con.requests.request.assert_called_once()  # pylint: disable=no-member
    con.time.sleep.assert_called()


def test_neon_request_non_attendees_endpoint(mocker, c):
    """Test endpoint without ratelimiting"""
    con.requests.request.return_value = mocker.Mock(
        status_code=200, json=lambda: {"key": "value"}
    )
    assert c.neon_request("api_key", "/other_endpoint") == {"key": "value"}
    con.requests.request.assert_called_once()  # pylint: disable=no-member
    con.time.sleep.assert_not_called()


def test_neon_request_retry_limit(mocker, c):
    """Test endpoint returning a non-ok response"""
    con.requests.request.return_value = mocker.Mock(
        status_code=404, content=b"Not Found"
    )
    with pytest.raises(RuntimeError, match="neon_request"):
        c.neon_request("api_key", "/other_endpoint")


def test_neon_request_retry_success(mocker, c):
    """Test endpoint returning a non-ok response"""
    con.requests.request.side_effect = [
        mocker.Mock(status_code=404, content=b"Not Found"),
        mocker.Mock(status_code=200, json=lambda: "ok"),
    ]
    assert c.neon_request("api_key", "/other_endpoint") == "ok"
    con.time.sleep.assert_called()


def test_bookstack_download(mocker, tmp_path, c):
    """Tests the bookstack_download method under happy path"""
    mocker.patch.object(
        con,
        "get_config",
        side_effect=lambda key: "mock_key" if "api_key" in key else "mock_url",
    )

    mock_response = mocker.MagicMock()
    mock_response.raw.stream.return_value = [b"test data"]
    mock_response.raise_for_status = mocker.Mock()
    mocker.patch.object(con.requests, "get", return_value=mock_response)

    dest = tmp_path / "testfile"
    file_size = c.bookstack_download("api_suffix", dest)

    assert file_size == len(b"test data")
    with open(dest, "rb") as f:
        assert f.read() == b"test data"
    mock_response.raise_for_status.assert_called_once()


def test_bookstack_download_zero_bytes(mocker, tmp_path, c):
    """Ensures exception thrown on zero-byte download"""
    mocker.patch.object(
        con,
        "get_config",
        side_effect=lambda key: "mock_key" if "api_key" in key else "mock_url",
    )

    mock_response = mocker.MagicMock()
    mock_response.raw.stream.return_value = [b""]
    mock_response.raise_for_status = mocker.Mock()
    mocker.patch.object(con.requests, "get", return_value=mock_response)

    dest = tmp_path / "testfile"

    with pytest.raises(ValueError):
        c.bookstack_download("api_suffix", dest)

    mock_response.raise_for_status.assert_called_once()


def test_bookstack_request_success(mocker):
    """Test bookstack_request with a successful JSON response"""
    mocker.patch.object(
        con,
        "get_config",
        side_effect=lambda v: {  # pylint: disable=unnecessary-lambda
            "bookstack/base_url": "http://example.com",
            "bookstack/api_key": "test-api-key",  # pragma: allowlist secret
            "connector/timeout": 5.0,
        }.get(v),
    )
    mock_request = mocker.patch.object(
        con.requests,
        "request",
        return_value=mocker.Mock(status_code=200, json=lambda: {"key": "value"}),
    )

    c = con.Connector()
    response = c.bookstack_request("GET", "/api/data")

    mock_request.assert_called_once_with(
        "GET",
        "http://example.com/api/data",
        headers={"X-Protohaven-Bookstack-API-Key": "test-api-key"},
        timeout=5.0,
    )
    assert response == {"key": "value"}


def test_bookstack_request_failure(mocker):
    """Test bookstack_request with a non-200 response"""
    mocker.patch.object(
        con,
        "get_config",
        side_effect=lambda v: {  # pylint: disable=unnecessary-lambda
            "bookstack/base_url": "http://example.com",
            "bookstack/api_key": "test-api-key",  # pragma: allowlist secret
            "connector/timeout": 5.0,
        }.get(v),
    )
    mocker.patch.object(
        con.requests,
        "request",
        return_value=mocker.Mock(status_code=404, content="Not Found"),
    )

    c = con.Connector()

    with pytest.raises(RuntimeError) as exc_info:
        c.bookstack_request("GET", "/api/data")

    assert "404: Not Found" in str(exc_info.value)
