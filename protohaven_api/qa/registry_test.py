"""Tests for the QA job registry."""

# pylint: disable=missing-function-docstring

from protohaven_api.qa.registry import ALL_JOBS, get_job, jobs_by_category


def test_all_jobs_have_unique_names():
    names = [s.name for s in ALL_JOBS]
    assert len(names) == len(set(names))


def test_categories_and_destructive_flag():
    cats = jobs_by_category()
    assert {"probers", "readonly", "asana_tasks", "additive", "destructive"} <= set(
        cats.keys()
    )
    assert all(s.destructive for s in cats["destructive"])


def test_get_job():
    assert get_job("probe_events") is not None
    assert get_job("does_not_exist") is None
