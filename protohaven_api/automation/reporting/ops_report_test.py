"""Unit tests for ops_report module"""

import datetime

from protohaven_api.automation.reporting import ops_report
from protohaven_api.testing import d


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
        return [ops_report.OpsItem(category="Override", label="Test Item", value="5")]

    result = test_function()
    assert len(result) == 1
    assert result[0].category == "Override"  # Explicit value should win
    assert result[0].source == "Default Source"  # Default should apply


def test_get_asana_assets_success(mocker):
    """Test successful asset reporting"""
    mocker.patch.object(
        ops_report.tasks,
        "get_asset_disposal",
        return_value=[
            {"name": "A1", "sections": ["unlisted"]},
            {"name": "A2", "sections": ["listed"]},
        ],
    )
    result = ops_report.get_asana_assets()
    assert len(result) == 2
    assert result[0].label == "Unlisted assets"
    assert result[0].value == "1"
    assert result[1].label == "Unsold listings"
    assert result[1].value == "1"


def test_get_asana_instructor_apps_success(mocker):
    """Test successful instructor applications reporting"""
    mocker.patch.object(
        ops_report.tasks,
        "get_with_onhold_section",
        return_value=[
            {"name": "App 1", "modified_at": d(0)},
            {"name": "App 2", "modified_at": d(-15)},
        ],
    )
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    result = ops_report.get_asana_instructor_apps()

    assert len(result) == 1
    assert result[0].label == "Stalled applications (>2wks)"
    assert result[0].value == "1"


def test_get_asana_instructor_apps_error(mocker):
    """Test error handling in instructor applications"""
    mocker.patch.object(
        ops_report.tasks,
        "get_with_onhold_section",
        side_effect=RuntimeError("API Error"),
    )
    result = ops_report.get_asana_instructor_apps()

    assert len(result) == 1
    assert result[0].value == "Error"
    assert isinstance(result[0].error, RuntimeError)


def test_get_asana_maint_tasks_success(mocker):
    """Test successful maintenance tasks reporting"""
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    mocker.patch.object(
        ops_report.tasks,
        "get_tech_ready_tasks",
        return_value=[
            ("Task 1", d(-15), []),
            ("Task 2", d(-1), ["on_hold"]),
            ("Task 3", d(-16), []),
        ],
    )
    result = ops_report.get_asana_maint_tasks()

    assert len(result) == 2
    assert result[0].label == "On hold maintenance tasks"
    assert result[0].value == "0"
    assert result[1].label == "Stale maintenance tasks (>2wks, no updates)"
    assert result[1].value == "2"


def test_get_asana_proposals_success(mocker):
    """Test successful project proposals reporting"""
    mocker.patch.object(
        ops_report.tasks,
        "get_project_requests",
        return_value=[
            {"name": "Project 1", "completed": False},
            {"name": "Project 2", "completed": True},
        ],
    )
    result = ops_report.get_asana_proposals()

    assert len(result) == 2
    assert result[0].label == "On hold"
    assert result[1].label == "Stale status (>2wks, no updates)"


def test_get_asana_tech_apps_success(mocker):
    """Test successful tech applications reporting"""
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    mocker.patch.object(
        ops_report.tasks,
        "get_with_onhold_section",
        return_value=[
            {"name": "Tech App 1", "modified_at": d(0)},
            {"name": "Tech App 2", "modified_at": d(-15)},
            {"name": "Tech App 3", "modified_at": d(-16)},
        ],
    )
    result = ops_report.get_asana_tech_apps()

    assert len(result) == 1
    assert result[0].label == "Stalled applications (>2wks)"
    assert result[0].value == "2"


def test_get_asana_purchase_requests_success(mocker):
    """Test successful purchase requests reporting"""
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    mocker.patch.object(
        ops_report.tasks,
        "get_purchase_requests",
        return_value=[
            {"name": "P1", "modified_at": d(0), "sections": []},
            {"name": "P2", "modified_at": d(-15), "sections": ["on_hold"]},
            {"name": "P3", "modified_at": d(-16), "sections": []},
        ],
    )
    result = ops_report.get_asana_purchase_requests()

    assert len(result) == 2
    assert result[0].label == "Purchase requests on hold"
    assert result[0].value == "1"
    assert result[1].label == "Purchase requests w/ no update (>2wks)"
    assert result[1].value == "2"


def test_get_ops_manager_sheet_inventory(mocker):
    """Test get_ops_manager_sheet_inventory returns correct OpsItems"""
    mock_items = [
        {"Recorded Qty": 5, "Target Qty": 10},
        {"Recorded Qty": 0, "Target Qty": 5},
        {"Recorded Qty": 10, "Target Qty": 10},
        {"Recorded Qty": 3, "Target Qty": 5},
        {"Recorded Qty": 1, "Target Qty": 2},
    ]
    mocker.patch.object(ops_report.sheets, "get_ops_inventory", return_value=mock_items)
    got = ops_report.get_ops_manager_sheet_inventory()
    assert len(got) == 2
    assert got[0].label == "Low stock"
    assert got[0].value == "3"
    assert got[1].label == "Out of stock"
    assert got[1].value == "1"


def test_get_ops_manager_sheet_inventory_no_issues(mocker):
    """Test get_ops_manager_sheet_inventory returns no color when no issues"""
    mock_items = [
        {"Recorded Qty": 10, "Target Qty": 10},
        {"Recorded Qty": 5, "Target Qty": 5},
    ]
    mocker.patch.object(ops_report.sheets, "get_ops_inventory", return_value=mock_items)
    got = ops_report.get_ops_manager_sheet_inventory()
    assert len(got) == 2
    assert got[0].label == "Low stock"
    assert got[0].value == "0"
    assert got[1].label == "Out of stock"
    assert got[1].value == "0"


def test_get_ops_manager_sheet_inventory_exception(mocker):
    """Test get_ops_manager_sheet_inventory handles exceptions"""
    mocker.patch.object(
        ops_report.sheets, "get_ops_inventory", side_effect=Exception("Test error")
    )
    got = ops_report.get_ops_manager_sheet_inventory()
    assert len(got) == 2
    assert got[0].label == "Low Stock"
    assert got[0].value == "Error"
    assert got[1].label == "Out of Stock"
    assert got[1].value == "Error"


def test_get_ops_manager_sheet_events(mocker):
    """Test get_ops_manager_sheet_events returns correct OpsItems"""
    mock_events = [
        {"Type": "Respirator QFT", "Date": d(-400)},
        {"Type": "HazCom", "Date": d(-200)},
        {"Type": "Tech Safety", "Date": d(-100)},
        {"Type": "Full Inventory", "Date": d(-20)},
        {"Type": "SDS Review", "Date": d(-300)},
    ]
    mocker.patch.object(
        ops_report.sheets, "get_ops_event_log", return_value=mock_events
    )
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    got = ops_report.get_ops_manager_sheet_events()
    assert len(got) == 5
    assert got[0].label == "Days until respirator QFT req'd"
    assert got[0].value == "-35"
    assert got[1].label == "Days until HazCom req'd"
    assert got[1].value == "165"
    assert got[2].label == "Days until volunteer safety training req'd"
    assert got[2].value == "265"
    assert got[3].label == "Days until full inventory req'd"
    assert got[3].value == "10"
    assert got[4].label == "Days until full SDS review req'd"
    assert got[4].value == "65"


def test_get_ops_manager_sheet_events_missing_events(mocker):
    """Test get_ops_manager_sheet_events handles missing event types"""
    mock_events = [
        {"Type": "Full Inventory", "Date": d(-40)},
    ]
    mocker.patch.object(
        ops_report.sheets, "get_ops_event_log", return_value=mock_events
    )
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    got = ops_report.get_ops_manager_sheet_events()
    assert len(got) == 5
    for item in got:
        if item.label == "Days until full inventory req'd":
            assert item.value == "-10"
        else:
            assert item.value == "0"


def test_get_ops_manager_sheet_events_exception(mocker):
    """Test get_ops_manager_sheet_events handles exceptions"""
    mocker.patch.object(
        ops_report.sheets, "get_ops_event_log", side_effect=Exception("Test error")
    )
    got = ops_report.get_ops_manager_sheet_events()
    assert len(got) == 5
    for item in got:
        assert item.value == "Error"


def test_get_ops_manager_sheet_budget(mocker):
    """Test get_ops_manager_sheet_budget returns correct OpsItems"""
    mock_budget = {
        "30 day spend rate": 1200,
        "monthly budget": 1500,
        "annual expenses": 8000,
        "annual budget": 10000,
    }
    mocker.patch.object(
        ops_report.sheets, "get_ops_budget_state", return_value=mock_budget
    )
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    got = ops_report.get_ops_manager_sheet_budget()
    assert len(got) == 2
    assert got[0].timescale == "30 days"
    assert got[0].label == "Spend rate"
    assert got[0].value == "$1200"
    assert got[0].target == "<$1500"
    assert got[1].timescale == "2025"
    assert got[1].label == "Annual budget spend"
    assert got[1].value == "$8000"
    assert got[1].target == "<$10000"


def test_get_ops_manager_sheet_budget_warning(mocker):
    """Test get_ops_manager_sheet_budget returns warning when over budget"""
    mock_budget = {
        "30 day spend rate": 2000,
        "monthly budget": 1500,
        "annual expenses": 12000,
        "annual budget": 10000,
    }
    mocker.patch.object(
        ops_report.sheets, "get_ops_budget_state", return_value=mock_budget
    )
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    got = ops_report.get_ops_manager_sheet_budget()
    assert len(got) == 2
    assert got[0].color == "warning"
    assert got[1].color == "warning"


def test_get_ops_manager_sheet_budget_exception(mocker):
    """Test get_ops_manager_sheet_budget handles exceptions"""
    mocker.patch.object(
        ops_report.sheets, "get_ops_budget_state", side_effect=Exception("Test error")
    )
    got = ops_report.get_ops_manager_sheet_budget()
    assert len(got) == 2
    assert got[0].label == "Spend rate"
    assert got[0].value == "Error"
    assert got[1].label == "Annual budget spend"
    assert got[1].value == "Error"


def test_get_airtable_violations_success(mocker):
    """Test successful violations reporting"""
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    mocker.patch.object(
        ops_report,
        "get_all_records",
        return_value=[
            {"fields": {"Closure": False, "Onset": d(-6).isoformat()}},
            {"fields": {"Closure": True, "Onset": d(-8).isoformat()}},
            {"fields": {"Closure": False, "Onset": d(-8).isoformat()}},
        ],
    )

    result = ops_report.get_airtable_violations()

    assert len(result) == 2
    assert result[0].label == "Open violations"
    assert result[0].value == "2"  # Two unresolved violations
    assert result[1].label == "Open and stale violations (>1wk)"
    assert result[1].value == "1"


def test_get_airtable_tool_info_success(mocker):
    """Test successful tool info reporting"""
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    mocker.patch.object(
        ops_report,
        "get_all_records",
        return_value=[
            {
                "fields": {
                    "Current Status": "Red",
                    "Status last modified": d(-8).isoformat(),
                }
            },
            {
                "fields": {
                    "Current Status": "Yellow",
                    "Status last modified": d(-15).isoformat(),
                }
            },
            {
                "fields": {
                    "Current Status": "Blue",
                    "Status last modified": d(0).isoformat(),
                }
            },
            {"fields": {"Current Status": "Grey"}},
        ],
    )

    result = ops_report.get_airtable_tool_info()

    assert len(result) == 3
    assert result[0].label == "Red tagged >7d"
    assert result[0].value == "1"
    assert result[1].label == "Yellow tagged >14d"
    assert result[1].value == "1"
    assert result[2].label == "Blue tagged"
    assert result[2].value == "1"


def test_get_airtable_instructor_capabilities_success(mocker):
    """Test successful instructor capabilities reporting"""
    mocker.patch.object(
        ops_report,
        "get_all_records",
        side_effect=(
            # clearance_codes
            [
                {"fields": {"Code": "C1"}},
                {"fields": {"Code": "C2"}},
                {"fields": {"Code": "C3"}},
            ],
            # capabilities
            [
                {
                    "fields": {
                        "Code (from Private Instruction)": ["C1", "C2"],
                        "W9 Form": "https://formurl",
                        "Direct Deposit Info": None,
                    }
                }
            ],
        ),
    )

    result = ops_report.get_airtable_instructor_capabilities()

    assert len(result) == 2
    assert result[0].label == "Unteachable clearances"
    assert result[0].value == "1"  # Two clearances with no active instructors
    assert result[1].label == "Missing paperwork"
    assert result[1].value == "1"  # One incomplete paperwork


def test_get_airtable_class_proposals_success(mocker):
    """Test successful class proposals reporting"""
    mocker.patch.object(ops_report, "tznow", return_value=d(0))
    mocker.patch.object(
        ops_report,
        "get_all_records",
        return_value=[
            {"fields": {"Approved": False, "Discontinued": False}},
            {"fields": {"Approved": True, "Discontinued": False}},
            {"fields": {"Approved": False, "Discontinued": True}},
        ],
    )

    result = ops_report.get_airtable_class_proposals()

    assert len(result) == 1
    assert result[0].label == "Unresolved class proposals"
    assert result[0].value == "1"


def test_get_shift_schedule_success(mocker):
    """Test successful shift schedule reporting"""
    now = d(0)
    mocker.patch.object(ops_report, "tznow", return_value=now)
    mocker.patch.object(
        ops_report.tauto,
        "generate",
        return_value={
            "calendar_view": [
                {"is_holiday": True, "AM": {"people": []}, "PM": {"people": []}},
                {
                    "is_holiday": False,
                    "AM": {"people": []},
                    "PM": {"people": ["A", "B"]},
                },
                {
                    "is_holiday": False,
                    "AM": {"people": ["A"]},
                    "PM": {"people": ["A", "B", "C"]},
                },
            ]
        },
    )

    result = ops_report.get_shift_schedule()

    assert len(result) == 2
    assert result[0].label == "Upcoming shifts with zero coverage"
    assert result[0].value == "1"  # One shift with 0 techs within 2 weeks
    assert result[1].label == "Upcoming shifts with low coverage (1 tech)"
    assert result[1].value == "1"  # One shift with 1 tech


def test_get_neon_tech_instructor_onboarding_success(mocker):
    """Test successful tech/instructor onboarding reporting"""
    now = d(0)
    mocker.patch.object(ops_report, "tznow", return_value=now)
    six_months_ago = now - datetime.timedelta(days=180)

    # Mock tech members
    mock_tech_members = [
        mocker.MagicMock(last_review=six_months_ago + datetime.timedelta(days=1)),
        mocker.MagicMock(last_review=six_months_ago - datetime.timedelta(days=1)),
    ]

    # Mock instructor members
    mock_instructor_members = [mocker.MagicMock()]
    mocker.patch.object(
        ops_report,
        "get_instructor_readiness",
        return_value={"v1": "not OK", "v2": "OK"},
    )
    mocker.patch.object(
        ops_report.neon,
        "search_members_with_role",
        side_effect=(mock_tech_members, mock_instructor_members),
    )

    result = ops_report.get_neon_tech_instructor_onboarding()

    assert len(result) == 2
    assert result[0].label == "Not fully onboarded"
    assert result[0].value == "1"  # One person not onboarded
    assert result[1].label == "Due for twice-annual review"
    assert result[1].value == "1"  # One person due for review


def test_get_neon_tech_instructor_onboarding_error(mocker):
    """Test error handling in tech/instructor onboarding"""
    mocker.patch.object(
        ops_report.neon,
        "search_members_with_role",
        side_effect=RuntimeError("Neon API Error"),
    )

    result = ops_report.get_neon_tech_instructor_onboarding()

    assert len(result) == 2
    for item in result:
        assert item.value == "Error"
        assert isinstance(item.error, RuntimeError)


def test_get_wiki_docs_status_success(mocker):
    """Test successful wiki docs status reporting"""
    mocker.patch.object(
        ops_report.wiki,
        "get_tool_docs_summary",
        return_value={
            "by_code": {
                "t1": {"clearance": None, "tool_tutorial": [{"approved_revision": 5}]},
                "t2": {"clearance": [{"approved_revision": 2}], "tool_tutorial": None},
                "t3": {
                    "clearance": [{"approved_revision": None}],
                    "tool_tutorial": [{"approved_revision": None}],
                },
            }
        },
    )
    result = ops_report.get_wiki_docs_status()

    assert len(result) == 3
    assert result[0].label == "Tool docs lacking approval"
    assert result[0].value == "2"
    assert result[1].label == "Missing clearance docs"
    assert result[1].value == "1"
    assert result[2].label == "Missing tool tutorials"
    assert result[2].value == "1"


def test_get_wiki_docs_status_error(mocker):
    """Test error handling in wiki docs status"""
    mocker.patch.object(
        ops_report.wiki,
        "get_tool_docs_summary",
        side_effect=RuntimeError("Wiki API Error"),
    )

    result = ops_report.get_wiki_docs_status()

    assert len(result) == 3
    for item in result:
        assert item.value == "Error"
        assert isinstance(item.error, RuntimeError)


def test_run_concurrent_execution(mocker):
    """Test that run function executes all reports concurrently"""
    mocker.patch.object(
        ops_report,
        "get_asana_assets",
        return_value=[ops_report.OpsItem(label="Test Asset", value="1")],
    )
    mocker.patch.object(
        ops_report,
        "get_wiki_docs_status",
        return_value=[ops_report.OpsItem(label="Test Wiki", value="2")],
    )

    results = list(ops_report.run())

    # Should get results from multiple functions
    assert len(results) > 0

    # Check that error strings are truncated to 256 chars
    for result in results:
        if result.error:
            assert len(result.error) <= 256
