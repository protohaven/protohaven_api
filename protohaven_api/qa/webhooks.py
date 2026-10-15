"""Post-deploy QA tests for Protohaven API webhooks.

These tests reuse the QA environment conventions from ``protohaven_api.qa``:

- comms are redirected to the internal QA Discord channel and email address
- webhook setup mutates ephemeral Neon accounts instead of the shared
  ``hello+test*`` accounts
- cleanup is registered on a :class:`CleanupStack` so mock data is removed
  even when an assertion fails
"""

import datetime
import logging
import os
import secrets
from dataclasses import dataclass, field
from typing import Any
from unittest import mock

import requests

from protohaven_api.app import configure_app
from protohaven_api.automation.membership import membership as memauto
from protohaven_api.config import load_yaml_with_env_substitution, tznow
from protohaven_api.integrations import airtable, neon, neon_base
from protohaven_api.qa.base import QA_CHANNEL, QA_EMAIL, CleanupStack
from protohaven_api.qa.fixtures import neon as neon_fixture

log = logging.getLogger("qa.webhooks")

ENV_OVERRIDE_KEYS = ("CHAN_OVERRIDE", "EMAIL_OVERRIDE", "NEW_MEMBERSHIP_ENABLED")
ENV_OVERRIDE_VALUES = {
    "CHAN_OVERRIDE": QA_CHANNEL,
    "EMAIL_OVERRIDE": QA_EMAIL,
    "NEW_MEMBERSHIP_ENABLED": "true",
}


def _set_qa_env_overrides() -> dict[str, str | None]:
    """Point comms and webhook initialization at QA targets."""
    old = {key: os.environ.get(key) for key in ENV_OVERRIDE_KEYS}
    os.environ.update(ENV_OVERRIDE_VALUES)
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    """Restore environment variables changed by :func:`_set_qa_env_overrides`."""
    for key, value in old.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@dataclass
class WebhookQAContext:
    """Runtime context for webhook QA tests."""

    api_key: str
    run_id: str = field(default_factory=lambda: secrets.token_hex(4))
    cleanup: CleanupStack = field(default_factory=CleanupStack)
    base_url: str | None = None
    verify_ssl: bool = True
    client: Any = None

    def __post_init__(self) -> None:
        self._old_env = _set_qa_env_overrides()
        # config.yaml substitution is cached, so clear it after changing env.
        load_yaml_with_env_substitution.cache_clear()
        if self.base_url is None and self.client is None:
            self.client = configure_app(
                session_secret=secrets.token_hex(16)
            ).test_client()

    def restore_comms_overrides(self) -> None:
        """Restore pre-QA environment variables."""
        _restore_env(self._old_env)
        load_yaml_with_env_substitution.cache_clear()

    # pylint: disable=too-many-arguments
    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make an authenticated request to the local or remote app."""
        headers = dict(headers or {})
        headers.setdefault("X-Protohaven-APIKey", self.api_key)
        if self.client is not None:
            return self.client.open(
                path,
                method=method,
                query_string=params,
                data=data,
                json=json,
                headers=headers,
            )

        url = f"{self.base_url.rstrip('/')}{path}"
        return requests.request(
            method,
            url,
            params=params,
            data=data,
            json=json,
            headers=headers,
            verify=self.verify_ssl,
            allow_redirects=False,
            timeout=30,
        )


def _response_text(rep: Any) -> str:
    """Return the body of a Flask or requests response as text."""
    if hasattr(rep, "text"):
        return rep.text
    return rep.get_data(as_text=True)


def _response_json(rep: Any) -> Any:
    """Return the parsed JSON body of a Flask or requests response."""
    if hasattr(rep, "json") and callable(rep.json):
        return rep.json()
    return rep.get_json()


def _do_clearance_req(ctx: WebhookQAContext, method: str, data: dict[str, str]):
    rep = ctx.request(method, "/user/clearances", params=data)
    log.info("%s %s: %s %s", method, data, rep.status_code, _response_text(rep))
    assert rep.status_code == 200, _response_text(rep)
    return rep


def test_clearance_webhook(ctx: WebhookQAContext) -> None:
    """Exercise the ``/user/clearances`` webhook with an ephemeral Neon account."""
    acct = neon_fixture.create_mock_account(ctx, "webhook-clearance")
    full_code = neon.resolve_clearance_code_full("FRG2")
    assert full_code, "FRG2 clearance code not found in Neon"

    def _get_codes() -> set[str]:
        rep = _do_clearance_req(ctx, "GET", {"emails": acct.email})
        return set(_response_json(rep)[acct.email]["result"])

    codes = _get_codes()
    if full_code in codes:
        _do_clearance_req(ctx, "DELETE", {"emails": acct.email, "codes": "FRG2"})
        _get_codes()

    _do_clearance_req(ctx, "PATCH", {"emails": acct.email, "codes": "FRG2"})
    codes = _get_codes()
    assert full_code in codes, codes

    _do_clearance_req(ctx, "DELETE", {"emails": acct.email, "codes": "FRG2"})
    codes = _get_codes()
    assert full_code not in codes, codes
    log.info("clearance webhook QA passed for %s", acct.email)


def test_new_member_webhook(ctx: WebhookQAContext, is_amp: bool = False) -> None:
    """Exercise the Neon membership-created webhook.

    A zero-cost membership is created first so the webhook can be invoked
    without Neon itself auto-deferring the membership. The webhook payload
    then supplies a paid fee to trigger the actual automation path.
    """
    acct = neon_fixture.create_mock_account(ctx, "webhook-new-member")
    start = tznow()
    mem = neon.create_zero_cost_membership(
        acct.neon_id, start, start + datetime.timedelta(days=30)
    )
    ctx.cleanup.register(
        f"delete Neon membership {mem['id']}",
        lambda: neon_base.delete("api_key2", f"/memberships/{mem['id']}"),
    )

    payload = {
        "customParameters": {"api_key": ctx.api_key},
        "data": {
            "membershipEnrollment": {
                "accountId": acct.neon_id,
                "membershipId": mem["id"],
                "membershipName": (
                    "General Membership - AMP" if is_amp else "General Membership"
                ),
                "fee": 35 if is_amp else 115,
                "enrollmentType": "JOIN",
            },
            "transaction": {"transactionStatus": "SUCCEEDED"},
        },
    }

    # The webhook normally creates an Eventbrite coupon. Use an ephemeral
    # coupon string so QA does not leave a real Eventbrite discount behind.
    with mock.patch.object(
        memauto, "fetch_new_member_coupon", return_value=f"QA-DISCOUNT-{ctx.run_id}"
    ):
        rep = ctx.request(
            "POST", "/admin/neon_membership_created_callback", json=payload
        )
    log.info(
        "new member webhook response: %s %s",
        rep.status_code,
        _response_text(rep),
    )
    assert rep.status_code == 200, _response_text(rep)

    acc = neon_base.fetch_account(acct.neon_id, required=True, fetch_memberships=True)
    membership = next(iter(acc.memberships()))
    assert (
        membership.start_date == memauto.PLACEHOLDER_START_DATE
    ), membership.start_date
    assert (acc.account_automation_ran or "").startswith(
        memauto.DEFERRED_STATUS
    ), acc.account_automation_ran
    log.info("new member webhook QA passed for %s", acct.email)


def test_maintenance_webhook(ctx: WebhookQAContext) -> None:
    """Exercise the Bookstack maintenance data webhook."""
    tool_code = next(
        t["fields"]["Tool Code"].strip()
        for t in airtable.get_tools()
        if t["fields"].get("Tool Code", "").strip()
    )
    rep = ctx.request(
        "GET",
        "/admin/get_maintenance_data",
        params={"tool_code": tool_code},
    )
    log.info(
        "maintenance webhook response: %s %s",
        rep.status_code,
        _response_text(rep),
    )
    assert rep.status_code == 200, _response_text(rep)
    body = _response_json(rep)
    assert "history" in body, body
    assert "active_tasks" in body, body
    log.info("maintenance webhook QA passed")
