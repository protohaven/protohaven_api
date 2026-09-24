"""Neon QA fixture helpers."""

from dataclasses import dataclass

from protohaven_api.integrations import neon
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
    return list(neon.search_members_by_email(QA_EMAIL_PREFIX, operator="CONTAINS"))


@dataclass
class MockNeonAccount:
    """Handle for a QA-created Neon account."""

    neon_id: str
    email: str
    name: str


def create_mock_account(ctx: QAContext, job: str) -> MockNeonAccount:
    """Create a uniquely identifiable Neon account and register cleanup."""
    email = qa_email(job, ctx.run_id)
    name = qa_name(job, ctx.run_id)
    neon_id = neon.create_member(name, email)
    ctx.cleanup.register(
        f"delete Neon account {neon_id}", lambda: neon.delete_account_unsafe(neon_id)
    )
    return MockNeonAccount(neon_id=neon_id, email=email, name=name)
