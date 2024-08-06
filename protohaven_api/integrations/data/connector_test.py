"""Tests for data connector"""
import pytest

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
    c = con.Connector(dev=False)
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
    c = con.Connector(dev=False)
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


def test_discord_dev_webhook():
    """Test that webhook returns an obj with raise_for_status in dev mode"""
    c = con.Connector(dev=True)
    rep = c.discord_webhook("test_webhook", "test_content")
    assert hasattr(rep, "raise_for_status")  # Needed in interpretation
