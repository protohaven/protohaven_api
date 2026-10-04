"""Tests for QA fixture helpers."""

# pylint: disable=missing-function-docstring

from protohaven_api.qa.fixtures import neon as neon_fixture


def test_qa_email_is_unique_and_searchable():
    email = neon_fixture.qa_email("sync-booked-members", "abc123")
    assert email == "hello+qa-cronicle-sync-booked-members-abc123@protohaven.org"
    assert email.startswith(neon_fixture.QA_EMAIL_PREFIX)


def test_search_qa_accounts_uses_contains(mocker):
    mock_search = mocker.patch.object(neon_fixture.neon, "search_members_by_email")
    neon_fixture.search_qa_accounts()
    mock_search.assert_called_once_with(
        neon_fixture.QA_EMAIL_PREFIX, operator="CONTAIN"
    )
