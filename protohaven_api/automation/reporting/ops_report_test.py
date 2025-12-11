"""Unit tests for ops_report module"""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from protohaven_api.automation.reporting import ops_report
from protohaven_api.testing import d, t


def test_opsitem_decorator_applies_defaults():
    """Test that opsitem decorator applies default values"""
    @ops_report.opsitem(category="Test", source="Test Source")
    def test_function():
        return [ops_report.OpsItem(label="Test Item", value="5")]

    result = test_function()
    assert len(result) == 1
    assert result[0].category == "Test"
    assert result[0].source == "Test Source"
    assert result[0].label == "Test Item"
    assert result[0].value == "5"

def test_opsitem_decorator_preserves_overrides():
    """Test that explicit values override defaults"""
    @ops_report.opsitem(category="Default", source="Default Source")
    def test_function():
        return [ops_report.OpsItem(
            category="Override",
            label="Test Item",
            value="5"
        )]

    result = test_function()
    assert len(result) == 1
    assert result[0].category == "Override"  # Explicit value should win
    assert result[0].source == "Default Source"  # Default should apply


def test_get_asana_assets_success():
    """Test successful asset reporting"""
    result = ops_report.get_asana_assets()

    assert len(result) == 2
    assert result[0].label == "Unlisted assets"
    assert result[0].target == "0"
    assert result[0].category == "Financial"
    assert result[1].label == "Unsold listings"
    assert result[1].target == "0"

@patch('protohaven_api.automation.reporting.ops_report.tasks.get_with_onhold_section')
def test_get_asana_instructor_apps_success(mock_get_onhold):
    """Test successful instructor applications reporting"""
    mock_get_onhold.return_value = [
        {"name": "App 1", "modified_at": "2024-01-01"},
        {"name": "App 2", "modified_at": "2024-01-01"}
    ]

    result = ops_report.get_asana_instructor_apps()

    assert len(result) == 1
    assert result[0].label == "Stalled applications (>2wks)"
    assert result[0].value == "2"
    assert result[0].category == "Instructor"
    mock_get_onhold.assert_called_once_with("instructor_applicants", exclude_on_hold=True, exclude_complete=True)

@patch('protohaven_api.automation.reporting.ops_report.tasks.get_with_onhold_section')
def test_get_asana_instructor_apps_error(mock_get_onhold):
    """Test error handling in instructor applications"""
    mock_get_onhold.side_effect = RuntimeError("API Error")

    result = ops_report.get_asana_instructor_apps()

    assert len(result) == 1
    assert result[0].value == "Error"
    assert isinstance(result[0].error, RuntimeError)

@patch('protohaven_api.automation.reporting.ops_report.tasks.get_tech_ready_tasks')
@patch('protohaven_api.automation.reporting.ops_report.tznow')
def test_get_asana_maint_tasks_success(mock_tznow, mock_get_tasks):
    """Test successful maintenance tasks reporting"""
    now = d(0)
    two_weeks_ago = now - datetime.timedelta(weeks=2)
    mock_tznow.return_value = now

    mock_get_tasks.return_value = [
        ("Task 1", two_weeks_ago - datetime.timedelta(days=1)),  # Stale
        ("Task 2", now - datetime.timedelta(days=1)),  # Not stale
        ("Task 3", two_weeks_ago - datetime.timedelta(days=5))   # Stale
    ]

    result = ops_report.get_asana_maint_tasks()

    assert len(result) == 2
    assert result[0].label == "On hold maintenance tasks"
    assert result[0].value == "0"  # No on-hold logic implemented yet
    assert result[1].label == "Stale maintenance tasks (>2wks, no updates)"
    assert result[1].value == "2"  # Two stale tasks

@patch('protohaven_api.automation.reporting.ops_report.tasks.get_project_requests')
def test_get_asana_proposals_success(mock_get_requests):
    """Test successful project proposals reporting"""
    mock_get_requests.return_value = [
        {"name": "Project 1", "completed": False},
        {"name": "Project 2", "completed": True}
    ]

    result = ops_report.get_asana_proposals()

    assert len(result) == 2
    assert result[0].label == "On hold"
    assert result[1].label == "Stale status (>2wks, no updates)"
    assert result[0].category == "Projects"

@patch('protohaven_api.automation.reporting.ops_report.tasks.get_with_onhold_section')
def test_get_asana_tech_apps_success(mock_get_onhold):
    """Test successful tech applications reporting"""
    mock_get_onhold.return_value = [
        {"name": "Tech App 1"},
        {"name": "Tech App 2"},
        {"name": "Tech App 3"}
    ]

    result = ops_report.get_asana_tech_apps()

    assert len(result) == 1
    assert result[0].label == "Stalled applications (>2wks)"
    assert result[0].value == "3"
    assert result[0].category == "Tech"

def test_get_asana_purchase_requests_success():
    """Test successful purchase requests reporting"""
    result = ops_report.get_asana_purchase_requests()

    assert len(result) == 2
    assert result[0].label == "Purchase requests on hold"
    assert result[0].value == "0"  # Placeholder implementation
    assert result[1].label == "Purchase requests w/ no update (>2wks)"
    assert result[1].value == "0"  # Placeholder implementation
    assert result[0].category == "Inventory"


@patch('protohaven_api.automation.reporting.ops_report.tznow')
def test_get_ops_manager_sheet_success(mock_tznow):
    """Test successful ops manager sheet reporting"""
    mock_tznow.return_value = d(0)  # 2025-01-01

    result = ops_report.get_ops_manager_sheet()

    assert len(result) == 7
    labels = [item.label for item in result]
    assert "Spend rate" in labels
    assert "Days until volunteer safety training req'd" in labels
    assert "Low stock" in labels
    assert "Out of stock" in labels

    # Check financial item has correct year
    financial_item = next(item for item in result if item.label == "Spend rate")
    assert financial_item.timescale == "2025"
    assert financial_item.category == "Financial"

@patch('protohaven_api.automation.reporting.ops_report.tznow')
def test_get_ops_manager_sheet_error(mock_tznow):
    """Test error handling in ops manager sheet"""
    mock_tznow.side_effect = RuntimeError("Time error")

    result = ops_report.get_ops_manager_sheet()

    assert len(result) == 7
    for item in result:
        assert item.value == "Error"
        assert isinstance(item.error, RuntimeError)


@patch('protohaven_api.automation.reporting.ops_report.get_all_records')
@patch('protohaven_api.automation.reporting.ops_report.tznow')
def test_get_airtable_violations_success(mock_tznow, mock_get_records):
    """Test successful violations reporting"""
    mock_tznow.return_value = d(0)
    mock_get_records.return_value = [
        {"fields": {"Resolved": False, "Created time": "2024-12-01"}},
        {"fields": {"Resolved": True, "Created time": "2024-12-01"}},
        {"fields": {"Resolved": False, "Created time": "2024-11-01"}}
    ]

    result = ops_report.get_airtable_violations()

    assert len(result) == 2
    assert result[0].label == "Open violations"
    assert result[0].value == "2"  # Two unresolved violations
    assert result[1].label == "Open and stale violations (>1wk)"
    assert result[0].category == "Inventory"
    mock_get_records.assert_called_once_with("policy_enforcement", "violations")

@patch('protohaven_api.automation.reporting.ops_report.get_all_records')
def test_get_airtable_tool_info_success(mock_get_records):
    """Test successful tool info reporting"""
    mock_get_records.return_value = [
        {"fields": {"Tag Status": "Red", "Tag Date": "2024-12-01"}},
        {"fields": {"Tag Status": "Yellow", "Tag Date": "2024-11-15"}},
        {"fields": {"Tag Status": "Blue", "Tag Date": "2024-12-01"}},
        {"fields": {"Tag Status": "Green"}}
    ]

    result = ops_report.get_airtable_tool_info()

    assert len(result) == 4
    labels = [item.label for item in result]
    assert "Red tagged >7d" in labels
    assert "Yellow tagged >14d" in labels
    assert "Blue tagged" in labels
    assert "Physical/digital tag mismatches corrected" in labels

    # Blue tagged count should be 1
    blue_item = next(item for item in result if item.label == "Blue tagged")
    assert blue_item.value == "1"
    assert blue_item.category == "Equipment"

@patch('protohaven_api.automation.reporting.ops_report.get_all_records')
def test_get_airtable_instructor_capabilities_success(mock_get_records):
    """Test successful instructor capabilities reporting"""
    mock_get_records.return_value = [
        {"fields": {"Active Instructors": [], "Paperwork Complete": False}},
        {"fields": {"Active Instructors": ["Instructor 1"], "Paperwork Complete": True}},
        {"fields": {"Active Instructors": [], "Paperwork Complete": True}}
    ]

    result = ops_report.get_airtable_instructor_capabilities()

    assert len(result) == 2
    assert result[0].label == "Unteachable clearances"
    assert result[0].value == "2"  # Two clearances with no active instructors
    assert result[1].label == "Missing paperwork"
    assert result[1].value == "1"  # One incomplete paperwork
    assert result[0].category == "Instructors"

@patch('protohaven_api.automation.reporting.ops_report.get_all_records')
@patch('protohaven_api.automation.reporting.ops_report.tznow')
def test_get_airtable_class_proposals_success(mock_tznow, mock_get_records):
    """Test successful class proposals reporting"""
    mock_tznow.return_value = d(0)
    mock_get_records.return_value = [
        {"fields": {"Status": "Proposed", "Last Modified": "2024-11-01"}},
        {"fields": {"Status": "Approved", "Last Modified": "2024-11-01"}},
        {"fields": {"Status": "Under Review", "Last Modified": "2024-11-01"}}
    ]

    result = ops_report.get_airtable_class_proposals()

    assert len(result) == 1
    assert result[0].label == "Stale proposals (>2wks, no update)"
    assert result[0].value == "2"  # Two proposals in review status
    assert result[0].category == "Instructors"

@patch('protohaven_api.automation.reporting.ops_report.get_all_records')
@patch('protohaven_api.automation.reporting.ops_report.tznow')
def test_get_shift_schedule_success(mock_tznow, mock_get_records):
    """Test successful shift schedule reporting"""
    now = d(0)
    mock_tznow.return_value = now
    two_weeks_from_now = now + datetime.timedelta(weeks=2)

    mock_get_records.return_value = [
        {"fields": {"Date": now.date(), "Tech Count": 0}},
        {"fields": {"Date": (now + datetime.timedelta(days=7)).date(), "Tech Count": 1}},
        {"fields": {"Date": (now + datetime.timedelta(days=14)).date(), "Tech Count": 2}},
        {"fields": {"Date": (now + datetime.timedelta(days=21)).date(), "Tech Count": 0}}  # Beyond 2 weeks
    ]

    result = ops_report.get_shift_schedule()

    assert len(result) == 2
    assert result[0].label == "Upcoming shifts with zero coverage"
    assert result[0].value == "1"  # One shift with 0 techs within 2 weeks
    assert result[1].label == "Upcoming shifts with low coverage (1 tech)"
    assert result[1].value == "1"  # One shift with 1 tech
    assert result[0].category == "Techs"

@patch('protohaven_api.automation.reporting.ops_report.neon.search_members_with_role')
@patch('protohaven_api.automation.reporting.ops_report.tznow')
def test_get_neon_tech_instructor_onboarding_success(mock_tznow, mock_search_role):
    """Test successful tech/instructor onboarding reporting"""
    now = d(0)
    mock_tznow.return_value = now
    six_months_ago = now - datetime.timedelta(days=180)

    # Mock tech members
    mock_tech_members = [
        {"id": 1, "onboarding_complete": False, "last_review_date": six_months_ago - datetime.timedelta(days=1)},
        {"id": 2, "onboarding_complete": True, "last_review_date": six_months_ago - datetime.timedelta(days=30)}
    ]

    # Mock instructor members
    mock_instructor_members = [
        {"id": 3, "onboarding_complete": True, "last_review_date": now - datetime.timedelta(days=30)}
    ]

    def mock_search_side_effect(role):
        if role == "Shop Tech":
            return mock_tech_members
        elif role == "Instructor":
            return mock_instructor_members
        return []

    mock_search_role.side_effect = mock_search_side_effect

    result = ops_report.get_neon_tech_instructor_onboarding()

    assert len(result) == 2
    assert result[0].label == "Not fully onboarded"
    assert result[0].value == "1"  # One person not onboarded
    assert result[1].label == "Due for twice-annual review"
    assert result[1].value == "1"  # One person due for review
    assert result[0].category == "Techs"

@patch('protohaven_api.automation.reporting.ops_report.neon.search_members_with_role')
def test_get_neon_tech_instructor_onboarding_error(mock_search_role):
    """Test error handling in tech/instructor onboarding"""
    mock_search_role.side_effect = RuntimeError("Neon API Error")

    result = ops_report.get_neon_tech_instructor_onboarding()

    assert len(result) == 2
    for item in result:
        assert item.value == "Error"
        assert isinstance(item.error, RuntimeError)

@patch('protohaven_api.automation.reporting.ops_report.wiki.get_class_docs_report')
@patch('protohaven_api.automation.reporting.ops_report.wiki.get_tool_docs_summary')
def test_get_wiki_docs_status_success(mock_tool_docs, mock_class_docs):
    """Test successful wiki docs status reporting"""
    mock_tool_docs.return_value = {
        "lacking_approval": 3,
        "missing_tutorials": 2
    }
    mock_class_docs.return_value = {
        "missing_clearance_docs": 1
    }

    result = ops_report.get_wiki_docs_status()

    assert len(result) == 3
    assert result[0].label == "Tool docs lacking approval"
    assert result[0].value == "3"
    assert result[1].label == "Missing clearance docs"
    assert result[1].value == "1"
    assert result[2].label == "Missing tool tutorials"
    assert result[2].value == "2"
    assert result[0].category == "Documentation"

@patch('protohaven_api.automation.reporting.ops_report.wiki.get_tool_docs_summary')
def test_get_wiki_docs_status_error(mock_tool_docs):
    """Test error handling in wiki docs status"""
    mock_tool_docs.side_effect = RuntimeError("Wiki API Error")

    result = ops_report.get_wiki_docs_status()

    assert len(result) == 3
    for item in result:
        assert item.value == "Error"
        assert isinstance(item.error, RuntimeError)


@patch('protohaven_api.automation.reporting.ops_report.get_wiki_docs_status')
@patch('protohaven_api.automation.reporting.ops_report.get_asana_assets')
def test_run_concurrent_execution(mock_assets, mock_wiki):
    """Test that run function executes all reports concurrently"""
    mock_assets.return_value = [ops_report.OpsItem(label="Test Asset", value="1")]
    mock_wiki.return_value = [ops_report.OpsItem(label="Test Wiki", value="2")]

    results = list(ops_report.run())

    # Should get results from multiple functions
    assert len(results) > 0

    # Check that error strings are truncated to 256 chars
    for result in results:
        if result.error:
            assert len(result.error) <= 256

@patch('protohaven_api.automation.reporting.ops_report.get_asana_assets')
def test_run_error_truncation(mock_assets):
    """Test that run function truncates long error messages"""
    long_error = RuntimeError("x" * 500)  # Very long error message
    mock_assets.return_value = [
        ops_report.OpsItem(label="Test", value="Error", error=long_error)
    ]

    results = list(ops_report.run())

    # Find the result with error
    error_result = next(r for r in results if r.error)
    assert len(error_result.error) <= 256
    assert error_result.error.startswith("x")

@patch('protohaven_api.automation.reporting.ops_report.get_asana_assets')
def test_run_string_error_handling(mock_assets):
    """Test that run function handles non-Exception errors"""
    mock_assets.return_value = [
        ops_report.OpsItem(label="Test", value="Error", error="String error")
    ]

    results = list(ops_report.run())

    # Should handle string errors gracefully
    error_result = next(r for r in results if r.error)
    assert error_result.error == "String error"
