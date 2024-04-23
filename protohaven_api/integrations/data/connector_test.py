import pytest

from protohaven_api.integrations.data import connector as con


def test_airtable_read_retry(mocker):
    mocker.patch.object(con.time, "sleep")
    mocker.patch.object(
        con.requests,
        "request",
        side_effect=[con.requests.exceptions.ReadTimeout("Whoopsie"), True],
    )
    c = con.Connector(dev=False)
    assert c.airtable_request("token", "GET", "URL") is True
    con.time.sleep.assert_called()


def test_airtable_read_max_retries(mocker):
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
    with pytest.raises(con.requests.exceptions.ReadTimeout):
        c.airtable_request("token", "GET", "URL")
