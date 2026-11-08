"""Tests for QA fixture helpers."""

# pylint: disable=duplicate-code,missing-function-docstring,protected-access

import pytest

from protohaven_api.qa.fixtures import airtable as airtable_fixture
from protohaven_api.qa.fixtures import neon as neon_fixture
from protohaven_api.testing import d


def test_qa_email_is_unique_and_searchable():
    email = neon_fixture.qa_email("sync-booked-members", "abc123")
    assert email == "qa-testing+qa-cronicle-sync-booked-members-abc123@protohaven.org"
    assert email.startswith(neon_fixture.QA_EMAIL_PREFIX)


def test_deleted_qa_email_is_unique_and_searchable():
    email = neon_fixture.deleted_qa_email("abc123", "3590")
    assert email == "qa-deleted-abc123-3590@protohaven.org"
    assert email.startswith(neon_fixture.QA_DELETED_EMAIL_PREFIX)


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


def test_search_deleted_qa_accounts_uses_contains(mocker):
    mock_search = mocker.patch.object(
        neon_fixture.neon, "search_members_by_email", return_value=[]
    )
    neon_fixture.search_deleted_qa_accounts()
    mock_search.assert_called_once_with(
        neon_fixture.QA_DELETED_EMAIL_PREFIX, operator="CONTAIN"
    )


def test_search_deleted_qa_accounts_rejects_member_agreement(mocker):
    mocker.patch.object(
        neon_fixture.neon,
        "search_members_by_email",
        return_value=[
            mocker.Mock(neon_id="3590", member_agreement_accepted=("v1", d(0)))
        ],
    )
    with pytest.raises(RuntimeError, match="member agreement is signed"):
        neon_fixture.search_deleted_qa_accounts()


def test_search_deleted_qa_accounts_accepts_unsigned_accounts(mocker):
    acct = mocker.Mock(neon_id="3590", member_agreement_accepted=(None, None))
    mocker.patch.object(
        neon_fixture.neon, "search_members_by_email", return_value=[acct]
    )
    assert neon_fixture.search_deleted_qa_accounts() == [acct]


def test_clear_account_cart_deletes_active_cart_orders(mocker):
    fetch = mocker.patch.object(
        neon_fixture.neon_base,
        "paginated_fetch",
        return_value=[
            {"id": "1", "status": "Pending"},
            {"id": "2", "status": "Succeeded"},
            {"id": "3", "status": "Processing"},
        ],
    )
    delete = mocker.patch.object(neon_fixture.neon_base, "delete")

    neon_fixture._clear_account_cart("3590")

    fetch.assert_called_once_with("api_key2", "/accounts/3590/orders")
    assert delete.call_args_list == [
        mocker.call("api_key2", "/orders/1"),
        mocker.call("api_key2", "/orders/3"),
    ]


def test_reuse_deleted_account_patches_primary_contact(mocker):
    clear_cart = mocker.patch.object(neon_fixture, "_clear_account_cart")
    patch = mocker.patch.object(neon_fixture.neon_base, "patch_account")
    neon_fixture.reuse_deleted_account(
        "3590",
        "qa-testing+qa-cronicle-sync-booked-members-abc123@protohaven.org",
        "QA Cronicle sync-booked-members abc123",
    )
    clear_cart.assert_called_once_with("3590")
    patch.assert_called_once_with(
        "3590",
        {
            "primaryContact": {
                "email1": "qa-testing+qa-cronicle-sync-booked-members-abc123@protohaven.org",
                "firstName": "QA Cronicle",
                "lastName": "sync-booked-members abc123",
            },
            "accountCustomFields": [
                {"id": str(neon_fixture.neon.CustomField.DISCORD_USER), "value": ""},
                {"id": str(neon_fixture.neon.CustomField.BOOKED_USER_ID), "value": ""},
            ],
        },
    )


def test_create_mock_account_reuses_deleted_account(mocker):
    ctx = mocker.Mock(run_id="abc123")
    mocker.patch.object(
        neon_fixture,
        "search_deleted_qa_accounts",
        return_value=[mocker.Mock(neon_id="3590")],
    )
    reuse = mocker.patch.object(neon_fixture, "reuse_deleted_account")
    create = mocker.patch.object(neon_fixture.neon, "create_member")

    acct = neon_fixture.create_mock_account(ctx, "sync-booked-members")

    reuse.assert_called_once_with(
        "3590",
        "qa-testing+qa-cronicle-sync-booked-members-abc123@protohaven.org",
        "QA Cronicle sync-booked-members abc123",
    )
    create.assert_not_called()
    assert acct == neon_fixture.MockNeonAccount(
        neon_id="3590",
        email="qa-testing+qa-cronicle-sync-booked-members-abc123@protohaven.org",
        name="QA Cronicle sync-booked-members abc123",
    )
    ctx.cleanup.register.assert_called_once()


def test_create_mock_account_skips_deleted_accounts_without_ids(mocker):
    ctx = mocker.Mock(run_id="abc123")
    mocker.patch.object(
        neon_fixture,
        "search_deleted_qa_accounts",
        return_value=[mocker.Mock(neon_id=None), mocker.Mock(neon_id="3590")],
    )
    reuse = mocker.patch.object(neon_fixture, "reuse_deleted_account")
    create = mocker.patch.object(neon_fixture.neon, "create_member")

    neon_fixture.create_mock_account(ctx, "sync-booked-members")

    reuse.assert_called_once_with(
        "3590",
        "qa-testing+qa-cronicle-sync-booked-members-abc123@protohaven.org",
        "QA Cronicle sync-booked-members abc123",
    )
    create.assert_not_called()


def test_create_mock_account_creates_when_no_deleted_accounts(mocker):
    ctx = mocker.Mock(run_id="abc123")
    mocker.patch.object(neon_fixture, "search_deleted_qa_accounts", return_value=[])
    create = mocker.patch.object(
        neon_fixture.neon, "create_member", return_value="3600"
    )

    acct = neon_fixture.create_mock_account(ctx, "sync-booked-members")

    create.assert_called_once_with(
        "QA Cronicle",
        "qa-testing+qa-cronicle-sync-booked-members-abc123@protohaven.org",
        last_name="sync-booked-members abc123",
    )
    assert acct == neon_fixture.MockNeonAccount(
        neon_id="3600",
        email="qa-testing+qa-cronicle-sync-booked-members-abc123@protohaven.org",
        name="QA Cronicle sync-booked-members abc123",
    )
    ctx.cleanup.register.assert_called_once()


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
            },
            "accountCustomFields": [
                {"id": str(neon_fixture.neon.CustomField.DISCORD_USER), "value": ""},
                {"id": str(neon_fixture.neon.CustomField.BOOKED_USER_ID), "value": ""},
            ],
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


def test_create_violation_sets_neon_id_as_integer(mocker):
    ctx = mocker.Mock()
    mocker.patch.object(
        airtable_fixture.airtable_base,
        "get_connector",
        return_value=mocker.Mock(**{"db_format.return_value": "nocodb"}),
    )
    mocker.patch.object(
        airtable_fixture.airtable,
        "get_policy_sections",
        return_value=[{"id": "123"}],
    )
    insert = mocker.patch.object(
        airtable_fixture.airtable_base,
        "insert_records",
        return_value=(200, {"records": [{"id": "rec_violation"}]}),
    )
    got = airtable_fixture.create_violation(ctx, "3646", onset=d(0))
    assert got == "rec_violation"
    fields = insert.call_args.args[0][0]
    assert fields["Neon ID"] == 3646
    assert isinstance(fields["Neon ID"], int)


def test_create_tool_record_sets_shop_area_link(mocker):
    ctx = mocker.Mock()
    mocker.patch.object(
        airtable_fixture.airtable,
        "get_areas",
        return_value=[{"id": "rec_area", "fields": {"Name": "Woodshop"}}],
    )
    insert = mocker.patch.object(
        airtable_fixture, "insert_record", return_value="rec_tool"
    )
    got = airtable_fixture.create_tool_record(
        ctx,
        tool_code="QA-123",
        tool_name="QA tool",
        area="Woodshop",
        booked_resource_id="123",
    )
    assert got == "rec_tool"
    fields = insert.call_args.args[3]
    assert fields["Shop Area"] == ["rec_area"]
    assert fields["Current Status"] == "Green (fully operational)"
    assert "Name (from Shop Area)" not in fields
