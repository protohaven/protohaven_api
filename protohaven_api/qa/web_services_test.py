"""Tests for the web service QA registry."""

# pylint: disable=missing-function-docstring

from protohaven_api.qa.web_services import PROD_ONLY_CHECKS


def test_prod_only_checks_are_present_and_unique():
    assert PROD_ONLY_CHECKS
    keys = [(c.path, c.description) for c in PROD_ONLY_CHECKS]
    assert len(keys) == len(set(keys))


def test_all_checks_have_descriptions():
    assert all(c.path and c.description for c in PROD_ONLY_CHECKS)
