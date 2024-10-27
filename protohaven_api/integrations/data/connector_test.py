"""Tests for data connector"""
import pytest
import requests
from requests.auth import HTTPBasicAuth

from protohaven_api.integrations.data import connector as con


def test_airtable_read_retry(mocker):
    """ReadTimeout triggers a retry on get requests to Airtable"""
    mocker.patch.object(con.time, "sleep")
    mocker.patch.object(
        con.requests,
        "request",
        side_effect=[
            con.requests.exceptions.ReadTimeout("Whoopsie"),
            mocker.MagicMock(status_code=200, content=True),
        ],
    )
    c = con.Connector()
    c.cfg = {
        "airtable": {
            "tools_and_equipment": {
                "token": "ASDF",
                "base_id": "GHJK",
                "tools": "TOOLS",
            }
        }
    }
    status, content = c.airtable_request("GET", "tools_and_equipment", "tools")
    assert status == 200
    assert content is True
    con.time.sleep.assert_called()


def test_airtable_read_max_retries(mocker):
    """Too many retries eventually causes a failure"""
    mocker.patch.object(con.time, "sleep")
    mocker.patch.object(
        con.requests,
        "request",
        side_effect=[
            con.requests.exceptions.ReadTimeout("Whoopsie"),
            con.requests.exceptions.ReadTimeout("Whoopsie again"),
            con.requests.exceptions.ReadTimeout("Last Fail"),
        ],
    )
    c = con.Connector()
    c.cfg = {
        "airtable": {
            "tools_and_equipment": {
                "token": "ASDF",
                "base_id": "GHJK",
                "tools": "TOOLS",
            }
        }
    }
    with pytest.raises(con.requests.exceptions.ReadTimeout):
        c.airtable_request("GET", "tools_and_equipment", "tools")


def test_neon_request_attendees_endpoint(mocker):
    mock_auth = mocker.patch("requests.auth.HTTPBasicAuth")
    mock_request = mocker.patch.object(
        requests,
        "request",
        return_value=mocker.Mock(status_code=200, json=lambda: {"key": "value"}),
    )
    mock_sleep = mocker.patch("time.sleep")

    connector = mocker.Mock()
    connector.neon_ratelimit = mocker.Mock()

    api_key = "test_api_key"
    args = ("/attendees",)
    result = neon_request(connector, api_key, *args)

    mock_auth.assert_called_once_with(get_config("neon/domain"), api_key)
    mock_request.assert_called_once_with(
        *args, auth=mock_auth.return_value, timeout=DEFAULT_TIMEOUT
    )
    mock_sleep.assert_called_once_with(0.25)
    assert result == {"key": "value"}


def test_neon_request_non_attendees_endpoint(mocker):
    mock_auth = mocker.patch("requests.auth.HTTPBasicAuth")
    mock_request = mocker.patch.object(
        requests,
        "request",
        return_value=mocker.Mock(status_code=200, json=lambda: {"key": "value"}),
    )

    connector = mocker.Mock()

    api_key = "test_api_key"
    args = ("/other_endpoint",)
    result = neon_request(connector, api_key, *args)

    mock_auth.assert_called_once_with(get_config("neon/domain"), api_key)
    mock_request.assert_called_once_with(
        *args, auth=mock_auth.return_value, timeout=DEFAULT_TIMEOUT
    )
    assert result == {"key": "value"}


def test_neon_request_non_200_response(mocker):
    mock_auth = mocker.patch("requests.auth.HTTPBasicAuth")
    mock_response = mocker.Mock(status_code=404, content=b"Not Found")
    mock_request = mocker.patch.object(requests, "request", return_value=mock_response)

    connector = mocker.Mock()

    api_key = "test_api_key"
    args = ("/other_endpoint",)

    with pytest.raises(RuntimeError, match="neon_request"):
        neon_request(connector, api_key, *args)

    mock_auth.assert_called_once_with(get_config("neon/domain"), api_key)
    mock_request.assert_called_once_with(
        *args, auth=mock_auth.return_value, timeout=DEFAULT_TIMEOUT
    )
