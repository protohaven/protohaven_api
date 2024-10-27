"""Tests for data connector"""
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
        mocker.MagicMock(status_code=200, content=True),
    ]
    status, content = c.airtable_request("GET", "tools_and_equipment", "tools")
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
        c.airtable_request("GET", "tools_and_equipment", "tools")


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


def test_neon_request_non_200_response(mocker, c):
    """Test endpoint returning a non-ok response"""
    con.requests.request.return_value = mocker.Mock(
        status_code=404, content=b"Not Found"
    )
    with pytest.raises(RuntimeError, match="neon_request"):
        c.neon_request("api_key", "/other_endpoint")
