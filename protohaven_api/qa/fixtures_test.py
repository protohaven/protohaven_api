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


def test_anonymize_mock_account_patches_primary_contact(mocker):
    patch = mocker.patch.object(neon_fixture.neon_base, "patch_account")
    neon_fixture.anonymize_mock_account("3590", "abc123")
    patch.assert_called_once_with(
        "3590",
        {
            "primaryContact": {
                "email1": "qa-deleted-abc123-3590@protohaven.org",
                "firstName": "QA Deleted",
                "lastName": "abc123-3590",
            }
        },
    )


def test_anonymize_legacy_qa_accounts_skips_missing_ids(mocker):
    acct = mocker.Mock(neon_id="3590")
    missing = mocker.Mock(neon_id=None)
    search = mocker.patch.object(
        neon_fixture, "search_qa_accounts", return_value=[acct, missing]
    )
    anonymize = mocker.patch.object(neon_fixture, "anonymize_mock_account")
    neon_fixture.anonymize_legacy_qa_accounts()
    search.assert_called_once_with()
    anonymize.assert_called_once_with("3590", "legacy-3590")
