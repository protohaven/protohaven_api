"""Tests for QA fixture helpers."""

# pylint: disable=missing-function-docstring

from protohaven_api.qa.fixtures import neon as neon_fixture


def test_qa_email_is_unique_and_searchable():
    email = neon_fixture.qa_email("sync-booked-members", "abc123")
    assert email == "qa-testing+qa-cronicle-sync-booked-members-abc123@protohaven.org"
    assert email.startswith(neon_fixture.QA_EMAIL_PREFIX)


def test_create_membership_omits_term_end_for_life_unit(mocker):
    post = mocker.patch.object(neon_fixture.neon_base, "post")
    neon_fixture.create_membership(
        "123", neon_fixture.datetime.datetime(2026, 10, 8), None, term_unit="LIFE"
    )
    payload = post.call_args.args[2]
    assert "termEndDate" not in payload
    assert payload["termUnit"] == "LIFE"


def test_create_membership_includes_term_end_for_dated_membership(mocker):
    post = mocker.patch.object(neon_fixture.neon_base, "post")
    neon_fixture.create_membership(
        "123",
        neon_fixture.datetime.datetime(2026, 10, 8),
        neon_fixture.datetime.datetime(2026, 11, 8),
    )
    payload = post.call_args.args[2]
    assert payload["termEndDate"] == "2026-11-08"
    assert payload["termUnit"] == "MONTH"


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


def test_create_membership_adds_payment_for_paid_membership(mocker):
    post = mocker.patch.object(neon_fixture.neon_base, "post")
    neon_fixture.create_membership(
        "123",
        neon_fixture.datetime.datetime(2026, 10, 8),
        neon_fixture.datetime.datetime(2026, 11, 8),
        fee=20,
    )
    payload = post.call_args.args[2]
    assert payload["payments"] == [
        {
            "amount": 20,
            "paymentStatus": "Succeeded",
            "note": "",
            "tenderType": 3,
            "receivedDate": None,
            "creditCardOnline": None,
            "creditCardOffline": None,
            "ach": None,
            "check": {
                "institution": "",
                "routingNumber": "",
                "accountNumber": None,
                "accountOwner": "QA Cronicle",
                "checkNumber": "",
                "accountType": "Checking",
            },
            "wire": None,
            "inKind": None,
            "dafpay": None,
        }
    ]


def test_create_membership_omits_payments_for_free_membership(mocker):
    post = mocker.patch.object(neon_fixture.neon_base, "post")
    neon_fixture.create_membership(
        "123",
        neon_fixture.datetime.datetime(2026, 10, 8),
        neon_fixture.datetime.datetime(2026, 11, 8),
    )
    payload = post.call_args.args[2]
    assert "payments" not in payload
