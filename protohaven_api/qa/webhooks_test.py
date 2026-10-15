"""Tests for the webhook QA harness."""

# pylint: disable=missing-function-docstring,too-few-public-methods,protected-access

import os

import pytest

from protohaven_api.qa import webhooks
from protohaven_api.qa.base import QA_CHANNEL, QA_EMAIL


class FakeResponse:
    """Test double for Flask/requests webhook responses."""

    def __init__(self, status_code=200, json_data=None, text="ok"):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def get_json(self):
        return self._json

    def get_data(self, as_text=False):
        return self.text if as_text else self.text.encode()


class FakeRequestsResponse:
    """Test double for a remote requests.Response."""

    def __init__(self, status_code=200, json_data=None, text="ok"):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


@pytest.fixture(name="ctx")
def fixture_ctx(mocker):
    old_env = {k: os.environ.get(k) for k in webhooks.ENV_OVERRIDE_KEYS}
    ctx = webhooks.WebhookQAContext(
        api_key="key",  # pragma: allowlist secret
        client=mocker.Mock(),
    )
    yield ctx
    ctx.restore_comms_overrides()
    assert all(os.environ.get(k) == v for k, v in old_env.items())


# pylint: disable=unused-argument
def test_context_sets_env_overrides(ctx):
    assert os.environ["CHAN_OVERRIDE"] == QA_CHANNEL
    assert os.environ["EMAIL_OVERRIDE"] == QA_EMAIL
    assert os.environ["NEW_MEMBERSHIP_ENABLED"] == "true"


def test_local_request_adds_api_key_header(ctx):
    ctx.client.open.return_value = FakeResponse()
    rep = ctx.request("GET", "/user/clearances", data={"emails": "a@b.com"})
    assert rep.status_code == 200
    ctx.client.open.assert_called_once_with(
        "/user/clearances",
        method="GET",
        query_string=None,
        data={"emails": "a@b.com"},
        json=None,
        headers={"X-Protohaven-APIKey": "key"},  # pragma: allowlist secret
    )


def test_remote_request(mocker):
    mock_requests = mocker.patch.object(webhooks.requests, "request")
    mock_requests.return_value = FakeRequestsResponse(
        json_data={"ok": True}, text='{"ok": true}'
    )
    ctx = webhooks.WebhookQAContext(
        api_key="key",  # pragma: allowlist secret
        base_url="https://staging.example",
        verify_ssl=False,
    )
    rep = ctx.request("POST", "/admin/neon_membership_created_callback", json={"x": 1})
    mock_requests.assert_called_once_with(
        "POST",
        "https://staging.example/admin/neon_membership_created_callback",
        params=None,
        data=None,
        json={"x": 1},
        headers={"X-Protohaven-APIKey": "key"},  # pragma: allowlist secret
        verify=False,
        allow_redirects=False,
        timeout=30,
    )
    assert webhooks._response_text(rep) == '{"ok": true}'
    assert webhooks._response_json(rep) == {"ok": True}
    ctx.restore_comms_overrides()


def test_clearance_webhook(ctx, mocker):
    acct = mocker.Mock(neon_id="123", email="qa@example.com")
    mocker.patch.object(webhooks.neon_fixture, "create_mock_account", return_value=acct)
    mocker.patch.object(
        webhooks.neon, "resolve_clearance_code_full", return_value="FRG: Forge"
    )
    responses = [
        FakeResponse(json_data={acct.email: {"result": []}}),
        FakeResponse(json_data={acct.email: {"result": []}}),
        FakeResponse(json_data={acct.email: {"result": ["FRG: Forge"]}}),
        FakeResponse(json_data={acct.email: {"result": []}}),
        FakeResponse(json_data={acct.email: {"result": []}}),
    ]
    ctx.request = mocker.Mock(side_effect=lambda method, path, **kw: responses.pop(0))

    webhooks.test_clearance_webhook(ctx)

    assert ctx.request.call_count == 5


def test_new_member_webhook(ctx, mocker):
    acct = mocker.Mock(neon_id="123", email="qa@example.com")
    mocker.patch.object(webhooks.neon_fixture, "create_mock_account", return_value=acct)
    mocker.patch.object(
        webhooks.neon, "create_zero_cost_membership", return_value={"id": "456"}
    )
    fetched = mocker.Mock()
    membership = mocker.Mock()
    membership.start_date = webhooks.memauto.PLACEHOLDER_START_DATE
    fetched.memberships.return_value = [membership]
    fetched.account_automation_ran = webhooks.memauto.DEFERRED_STATUS
    mocker.patch.object(webhooks.neon_base, "fetch_account", return_value=fetched)
    ctx.request = mocker.Mock(return_value=FakeResponse())
    ctx.cleanup = mocker.Mock()

    webhooks.test_new_member_webhook(ctx)

    ctx.cleanup.register.assert_called_once()
    ctx.request.assert_called_once_with(
        "POST", "/admin/neon_membership_created_callback", json=mocker.ANY
    )
    webhooks.neon_base.fetch_account.assert_called_once_with(  # pylint: disable=no-member
        acct.neon_id, required=True, fetch_memberships=True
    )


def test_maintenance_webhook(ctx, mocker):
    mocker.patch.object(
        webhooks.airtable,
        "get_tools",
        return_value=[{"fields": {"Tool Code": " SBL "}}],
    )
    ctx.request = mocker.Mock(
        return_value=FakeResponse(json_data={"history": [], "active_tasks": []})
    )
    webhooks.test_maintenance_webhook(ctx)
    ctx.request.assert_called_once_with(
        "GET",
        "/admin/get_maintenance_data",
        params={"tool_code": "SBL"},
    )
