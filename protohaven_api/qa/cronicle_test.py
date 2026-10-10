"""Tests for the QA Cronicle client."""

# pylint: disable=missing-function-docstring

import pytest

from protohaven_api.qa.cronicle import CronicleClient


def test_run_event_returns_ids(mocker):
    client = CronicleClient("https://cron.example", "key")
    mock_post = mocker.patch.object(client, "_post", return_value={"ids": ["j1", "j2"]})
    assert client.run_event("evt", "img", {"ARGS": "--help"}) == ["j1", "j2"]
    mock_post.assert_called_once_with(
        "/api/app/run_event/v2",
        {
            "id": "evt",
            "retries": 0,
            "timeout": client.job_timeout,
            "params": {"ARGS": "--help", "IMAGE": "img"},
        },
    )


def test_run_event_image_overrides_existing_image_param(mocker):
    client = CronicleClient("https://cron.example", "key")
    mock_post = mocker.patch.object(client, "_post", return_value={"ids": ["j1"]})
    assert client.run_event("evt", "img", {"IMAGE": "old", "ARGS": "--help"}) == ["j1"]
    mock_post.assert_called_once_with(
        "/api/app/run_event/v2",
        {
            "id": "evt",
            "retries": 0,
            "timeout": client.job_timeout,
            "params": {"IMAGE": "img", "ARGS": "--help"},
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
            "job output",
        ],
    )
    result = client.run_and_fetch_logs("evt", "img", {})
    assert result.code == 0
    assert result.job_ids == ["j1"]
    assert result.logs == {"j1": "job output"}
    assert result.text == "job output"


def test_run_and_fetch_logs_omits_full_logs_on_success(mocker):
    client = CronicleClient("https://cron.example", "key", poll_interval=0)
    mocker.patch.object(client, "_post", return_value={"ids": ["j1"]})
    mocker.patch.object(
        client,
        "_get",
        side_effect=[
            {"job": {"complete": 1, "code": 0}},
            "job output",
        ],
    )
    log_info = mocker.patch("protohaven_api.qa.cronicle.log.info")
    result = client.run_and_fetch_logs("evt", "img", {})
    assert result.code == 0
    assert result.text == "job output"
    assert any(
        "https://cron.example/#JobDetails?id=j1" in str(call)
        for call in log_info.call_args_list
    )
    assert all("job output" not in str(call) for call in log_info.call_args_list)


def test_run_and_fetch_logs_links_to_logs_on_failure(mocker):
    client = CronicleClient("https://cron.example", "key", poll_interval=0)
    mocker.patch.object(client, "_post", return_value={"ids": ["j1"]})
    mocker.patch.object(
        client,
        "_get",
        side_effect=[
            {"job": {"complete": 1, "code": 1}},
            "job failed output",
        ],
    )
    log_info = mocker.patch("protohaven_api.qa.cronicle.log.info")
    result = client.run_and_fetch_logs("evt", "img", {})
    assert result.code == 1
    assert result.text == "job failed output"
    assert any(
        "https://cron.example/#JobDetails?id=j1" in str(call)
        for call in log_info.call_args_list
    )
    assert all("job failed output" not in str(call) for call in log_info.call_args_list)


def test_run_and_fetch_logs_timeout(mocker):
    client = CronicleClient("https://cron.example", "key", poll_interval=0)
    mocker.patch.object(client, "_post", return_value={"ids": ["j1"]})
    mocker.patch.object(client, "_get", return_value={"job": {"complete": 0}})
    mocker.patch.object(client, "job_timeout", 0)
    with pytest.raises(TimeoutError):
        client.run_and_fetch_logs("evt", "img", {})
