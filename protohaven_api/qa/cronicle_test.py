"""Tests for the QA Cronicle client."""

import pytest

from protohaven_api.qa.cronicle import CronicleClient


def test_run_event_returns_ids(mocker):
    client = CronicleClient("https://cron.example", "key")
    mocker.patch.object(client, "_post", return_value={"ids": ["j1", "j2"]})
    assert client.run_event("evt", "img", {"ARGS": "--help"}) == ["j1", "j2"]
    client._post.assert_called_once_with(
        "/api/app/run_event/v2",
        {
            "id": "evt",
            "retries": 0,
            "timeout": client.job_timeout,
            "params": {"image": "img", "ARGS": "--help"},
        },
    )


def test_run_event_rejects_missing_ids(mocker):
    client = CronicleClient("https://cron.example", "key")
    mocker.patch.object(client, "_post", return_value={"error": "nope"})
    with pytest.raises(RuntimeError):
        client.run_event("evt", "img", {})


def test_run_and_fetch_logs_polls(mocker):
    client = CronicleClient("https://cron.example", "key", poll_interval=0)
    mocker.patch.object(client, "_post", return_value={"ids": ["j1"]})
    mocker.patch.object(
        client,
        "_get",
        side_effect=[
            {"job": {"complete": 0}},
            {"job": {"complete": 1, "code": 0}},
            {"text": "job output"},
        ],
    )
    result = client.run_and_fetch_logs("evt", "img", {})
    assert result.code == 0
    assert result.job_ids == ["j1"]
    assert result.logs == {"j1": "job output"}
    assert result.text == "job output"


def test_run_and_fetch_logs_timeout(mocker):
    client = CronicleClient("https://cron.example", "key", poll_interval=0)
    mocker.patch.object(client, "_post", return_value={"ids": ["j1"]})
    mocker.patch.object(
        client, "_get", return_value={"job": {"complete": 0}}
    )
    mocker.patch.object(client, "job_timeout", 0)
    with pytest.raises(TimeoutError):
        client.run_and_fetch_logs("evt", "img", {})
