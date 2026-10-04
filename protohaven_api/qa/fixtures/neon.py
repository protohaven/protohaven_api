"""Neon QA fixture helpers."""

# pylint: disable=too-many-arguments,too-many-positional-arguments

import datetime
from dataclasses import dataclass
from typing import Any

from protohaven_api.integrations import neon, neon_base
from protohaven_api.qa.base import QAContext

QA_EMAIL_PREFIX = "hello+qa-cronicle-"


def qa_email(job: str, run_id: str) -> str:
    """Build a unique, searchable QA Neon email address."""
    return f"{QA_EMAIL_PREFIX}{job}-{run_id}@protohaven.org"


def qa_name(job: str, run_id: str) -> str:
    """Build a unique, searchable QA Neon account name."""
    return f"QA Cronicle {job} {run_id}"


def search_qa_accounts():
    """Return all Neon accounts matching the QA email prefix."""
    return list(neon.search_members_by_email(QA_EMAIL_PREFIX, operator="CONTAIN"))


@dataclass
class MockNeonAccount:
    """Handle for a QA-created Neon account."""

    neon_id: str
    email: str
    name: str


def create_mock_account(ctx: QAContext, job: str) -> MockNeonAccount:
    """Create a uniquely identifiable Neon account and register cleanup.

    Follows the plan convention: first name is ``QA Cronicle`` and last name
    is ``<Job> <run_id>``.
    """
    email = qa_email(job, ctx.run_id)
    name = qa_name(job, ctx.run_id)
    neon_id = neon.create_member("QA Cronicle", email, last_name=f"{job} {ctx.run_id}")
    ctx.cleanup.register(
        f"delete Neon account {neon_id}", lambda: neon.delete_account_unsafe(neon_id)
    )
    return MockNeonAccount(neon_id=neon_id, email=email, name=name)


def create_membership(
    account_id: str,
    start: datetime.datetime,
    end: datetime.datetime | None,
    level: dict[str, Any] | None = None,
    term: dict[str, Any] | None = None,
    fee: int = 0,
    status: str = "SUCCEEDED",
) -> dict[str, Any]:
    """Create a membership for a mock Neon account.

    ``end`` may be ``None`` to deliberately create an active membership with
    no end date.
    """
    payload: dict[str, Any] = {
        "accountId": account_id,
        "membershipLevel": level or {"id": 1, "name": "General Membership"},
        "membershipTerm": term or {"id": 1, "name": "General - $115/mo (Join)"},
        "termStartDate": start.strftime("%Y-%m-%d"),
        "termUnit": "MONTH",
        "transactionDate": start.strftime("%Y-%m-%d"),
        "autoRenewal": False,
        "enrollType": "JOIN",
        "fee": fee,
        "totalCharge": fee,
        "status": status,
    }
    if end is not None:
        payload["termEndDate"] = end.strftime("%Y-%m-%d")
    return neon_base.post("api_key2", "/memberships", payload)


def register_for_event(
    ctx: QAContext, account_id: str, event_id: str, ticket_id: str
) -> None:
    """Register a mock Neon account for a QA event and register cleanup."""
    neon.register_for_event(account_id, event_id, ticket_id)
    ctx.cleanup.register(
        f"delete Neon registration for {account_id} in event {event_id}",
        lambda: neon.delete_single_ticket_registration(account_id, event_id),
    )
