"""Tests for final QA verification."""

# pylint: disable=missing-function-docstring

import pytest

from protohaven_api.qa import verify


def test_no_qa_neon_accounts_passes(mocker):
    mocker.patch.object(verify.neon_fixture, "search_qa_accounts", return_value=[])
    verify.verify_no_qa_neon_accounts()


def test_no_qa_neon_accounts_raises(mocker):
    acct = mocker.Mock(neon_id="123", email="hello+qa-cronicle-x-1@protohaven.org")
    mocker.patch.object(verify.neon_fixture, "search_qa_accounts", return_value=[acct])
    with pytest.raises(RuntimeError):
        verify.verify_no_qa_neon_accounts()
