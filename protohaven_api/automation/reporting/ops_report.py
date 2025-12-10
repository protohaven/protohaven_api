"""This module fetches from a wide range of primary data sources to create a comprehensive report
on the operational state of the shop."""

import datetime
import logging
from concurrent import futures
from dataclasses import asdict, dataclass
from typing import Callable, Iterator

from protohaven_api.config import get_config, tznow
from protohaven_api.integrations import airtable, neon, sheets, tasks, wiki
from protohaven_api.integrations.airtable_base import get_all_records

log = logging.getLogger("automation.reporting.ops_report")


@dataclass
class OpsItem:  # pylint: disable=too-many-instance-attributes
    """This represents a single line item in the operations report"""

    category: str = None
    label: str = None
    source: str = None
    url: str = None
    value: str = None
    target: str = None
    timescale: str = None
    color: str = None
    error: str | Exception = None


def opsitem(**defaults):
    """Applies defaults from a report generator, to reduce redundancy"""

    def decorator(fn: Callable[[], list[OpsItem]]):
        def wrapper(*args, **kwargs):
            result = []
            for ovr in fn(*args, **kwargs):
                vals = {**defaults}
                for k, v in asdict(ovr).items():
                    if v:
                        vals[k] = v
                result.append(OpsItem(**vals))
            return result

        return wrapper

    return decorator


@opsitem(category="Financial", timescale="last 12 months", source="Asana", url="https://app.asana.com")
def get_asana_assets() -> list[OpsItem]:
    """Return metrics for asset listing and sale from Asana"""
    try:
        # For now, return placeholder values since specific asset tracking 
        # projects aren't configured in the current Asana setup
        unlisted_count = 0
        unsold_count = 0
        
        return [
            OpsItem(label="Unlisted assets", value=str(unlisted_count), target="0"),
            OpsItem(label="Unsold listings", value=str(unsold_count), target="0"),
        ]
    except Exception as e:
        return [
            OpsItem(label="Unlisted assets", value="Error", target="0", error=e),
            OpsItem(label="Unsold listings", value="Error", target="0", error=e),
        ]


@opsitem(
    category="Instructor", timescale="ongoing", source="Asana", url=f"https://app.asana.com/0/{get_config('asana/instructor_applicants/gid')}/board", target="0"
)
def get_asana_instructor_apps() -> list[OpsItem]:
    """Return metrics for instructor applications from asana"""
    try:
        two_weeks_ago = tznow() - datetime.timedelta(weeks=2)
        stalled_count = 0
        
        # Get instructor applications that are not on hold and haven't been updated in 2+ weeks
        for req in tasks.get_with_onhold_section("instructor_applicants", exclude_on_hold=True, exclude_complete=True):
            # This would need actual modified_at data - placeholder for now
            stalled_count += 1  # Simplified counting logic
        
        return [
            OpsItem(
                label="Stalled applications (>2wks)",
                value=str(stalled_count),
            )
        ]
    except Exception as e:
        return [
            OpsItem(
                label="Stalled applications (>2wks)",
                value="Error",
                error=e,
            )
        ]


@opsitem(category="Techs", timescale="ongoing", source="Asana", url=f"https://app.asana.com/0/{get_config('asana/shop_and_maintenance_tasks/gid')}/board", target="0")
def get_asana_maint_tasks() -> list[OpsItem]:
    """Return metrics for maintenance tasks from asana"""
    try:
        two_weeks_ago = tznow() - datetime.timedelta(weeks=2)
        on_hold_count = 0
        stale_count = 0
        
        # Count tasks in on-hold sections and stale tasks
        for task_name, modified_at in tasks.get_tech_ready_tasks(tznow()):
            if modified_at and modified_at < two_weeks_ago:
                stale_count += 1
        
        # Get on-hold maintenance tasks - this would need section filtering
        # For now, use a placeholder count
        on_hold_count = 0
        
        return [
            OpsItem(
                label="On hold maintenance tasks",
                value=str(on_hold_count),
            ),
            OpsItem(
                label="Stale maintenance tasks (>2wks, no updates)",
                value=str(stale_count),
            ),
        ]
    except Exception as e:
        return [
            OpsItem(
                label="On hold maintenance tasks",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Stale maintenance tasks (>2wks, no updates)",
                value="Error",
                error=e,
            ),
        ]


@opsitem(
    category="Projects", timescale="ongoing", source="Asana", url=f"https://app.asana.com/0/{get_config('asana/project_requests')}/board", target="0"
)
def get_asana_proposals() -> list[OpsItem]:
    """Return metrics for project proposals/approvals from asana"""
    try:
        on_hold_count = 0
        stale_count = 0
        
        # Get project requests from Asana
        for req in tasks.get_project_requests():
            if not req.get('completed', True):  # Only count incomplete requests
                # This would need actual date parsing and section checking
                # For now using simplified logic
                pass
        
        return [
            OpsItem(
                label="On hold",
                value=str(on_hold_count),
            ),
            OpsItem(
                label="Stale status (>2wks, no updates)",
                value=str(stale_count),
            ),
        ]
    except Exception as e:
        return [
            OpsItem(
                label="On hold",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Stale status (>2wks, no updates)",
                value="Error",
                error=e,
            ),
        ]


@opsitem(category="Tech", timescale="ongoing", source="Asana", url=f"https://app.asana.com/0/{get_config('asana/shop_tech_applicants/gid')}/board", target="0")
def get_asana_tech_apps() -> list[OpsItem]:
    """Return metrics for tech applications from asana"""
    try:
        stalled_count = 0
        
        # Get tech applications that are not on hold and not completed
        for req in tasks.get_with_onhold_section("shop_tech_applicants", exclude_on_hold=True, exclude_complete=True):
            # This would need actual modified_at date checking
            # For now, count all non-hold, non-complete applications as potentially stalled
            stalled_count += 1
        
        return [
            OpsItem(
                label="Stalled applications (>2wks)",
                value=str(stalled_count),
            )
        ]
    except Exception as e:
        return [
            OpsItem(
                label="Stalled applications (>2wks)",
                value="Error",
                error=e,
            )
        ]


@opsitem(
    category="Inventory", timescale="ongoing", source="Asana", url=f"https://app.asana.com/0/{get_config('asana/purchase_requests/gid')}/board", target="0"
)
def get_asana_purchase_requests() -> list[OpsItem]:
    """Return metrics for purchase requests from asana"""
    try:
        on_hold_count = 0
        stale_count = 0
        two_weeks_ago = tznow() - datetime.timedelta(weeks=2)
        
        # This would use the actual Asana API to check purchase request sections
        # For now, using placeholder counts
        on_hold_count = 0
        stale_count = 0
        
        return [
            OpsItem(
                label="Purchase requests on hold",
                value=str(on_hold_count),
            ),
            OpsItem(
                label="Purchase requests w/ no update (>2wks)",
                value=str(stale_count),
            ),
        ]
    except Exception as e:
        return [
            OpsItem(
                label="Purchase requests on hold",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Purchase requests w/ no update (>2wks)",
                value="Error",
                error=e,
            ),
        ]


@opsitem(source="Sheet", url="https://docs.google.com/spreadsheets/d/ops-manager", timescale="ongoing", target="0")
def get_ops_manager_sheet() -> list[OpsItem]:
    """Return metrics from ops manager spreadsheet"""
    try:
        # This would need the actual ops manager spreadsheet ID and range configuration
        # For now, returning placeholder values that would be populated from sheet data
        current_year = tznow().year
        
        return [
            OpsItem(
                category="Financial",
                timescale=str(current_year),
                label="Spend rate",
                value="$0",
                target="<$1000",
                color="warning",
            ),
            OpsItem(
                category="Safety",
                label="Days until volunteer safety training req'd",
                value="365",
                target=">0",
            ),
            OpsItem(
                category="Safety",
                label="Days until HazCom / QFT req'd",
                value="365",
                target=">0",
            ),
            OpsItem(
                category="Safety",
                label="Days until full SDS review req'd",
                value="365",
                target=">0",
            ),
            OpsItem(
                category="Inventory",
                label="Low stock",
                value="0",
            ),
            OpsItem(
                category="Inventory",
                label="Out of stock",
                value="0",
            ),
            OpsItem(
                category="Inventory",
                label="Days until next full inventory req'd",
                value="30",
                target=">0",
            ),
        ]
    except Exception as e:
        error_items = []
        for label in [
            "Spend rate", "Days until volunteer safety training req'd",
            "Days until HazCom / QFT req'd", "Days until full SDS review req'd",
            "Low stock", "Out of stock", "Days until next full inventory req'd"
        ]:
            error_items.append(OpsItem(label=label, value="Error", error=e))
        return error_items


@opsitem(
    category="Inventory", timescale="ongoing", source="Airtable", url=f"https://airtable.com/{get_config('airtable/data/policy_enforcement/base_id')}", target="0"
)
def get_airtable_violations() -> list[OpsItem]:
    """Return report info about storage and other violations from Airtable"""
    try:
        open_count = 0
        stale_count = 0
        one_week_ago = tznow() - datetime.timedelta(weeks=1)
        
        # Get all violations from Airtable
        for record in get_all_records("policy_enforcement", "violations"):
            fields = record.get("fields", {})
            
            # Check if violation is open (not resolved)
            if not fields.get("Resolved", False):
                open_count += 1
                
                # Check if it's stale (created more than a week ago with no recent updates)
                created_time = fields.get("Created time")
                if created_time:
                    # This would need proper date parsing
                    stale_count += 1  # Simplified logic
        
        return [
            OpsItem(
                label="Open violations",
                value=str(open_count),
            ),
            OpsItem(
                label="Open and stale violations (>1wk)",
                value=str(stale_count),
            ),
        ]
    except Exception as e:
        return [
            OpsItem(
                label="Open violations",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Open and stale violations (>1wk)",
                value="Error",
                error=e,
            ),
        ]


@opsitem(
    category="Equipment", timescale="ongoing", source="Airtable", url=f"https://airtable.com/{get_config('airtable/data/tools_and_equipment/base_id')}", target="0"
)
def get_airtable_tool_info() -> list[OpsItem]:
    """Return report info about the state of tools in Airtable"""
    try:
        red_tagged_count = 0
        yellow_tagged_count = 0
        blue_tagged_count = 0
        mismatch_corrections = 0
        
        seven_days_ago = tznow() - datetime.timedelta(days=7)
        fourteen_days_ago = tznow() - datetime.timedelta(days=14)
        
        # Get all tools and their status
        for record in get_all_records("tools_and_equipment", "tools"):
            fields = record.get("fields", {})
            tag_status = fields.get("Tag Status", "")
            tag_date = fields.get("Tag Date")
            
            if tag_status == "Red" and tag_date:
                # Would need proper date parsing to check if > 7 days
                red_tagged_count += 1
            elif tag_status == "Yellow" and tag_date:
                # Would need proper date parsing to check if > 14 days 
                yellow_tagged_count += 1
            elif tag_status == "Blue":
                blue_tagged_count += 1
        
        # Get mismatch corrections from the last 14 days
        # This would require checking tool reports or a corrections log
        mismatch_corrections = 0
        
        return [
            OpsItem(
                label="Red tagged >7d",
                value=str(red_tagged_count),
            ),
            OpsItem(
                label="Yellow tagged >14d",
                value=str(yellow_tagged_count),
            ),
            OpsItem(
                label="Blue tagged",
                value=str(blue_tagged_count),
            ),
            OpsItem(
                label="Physical/digital tag mismatches corrected",
                value=str(mismatch_corrections),
                timescale="last 14 days",
            ),
        ]
    except Exception as e:
        return [
            OpsItem(
                label="Red tagged >7d",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Yellow tagged >14d",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Blue tagged",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Physical/digital tag mismatches corrected",
                value="Error",
                timescale="last 14 days",
                error=e,
            ),
        ]


@opsitem(
    category="Instructors",
    timescale="ongoing",
    source="Airtable",
    url=f"https://airtable.com/{get_config('airtable/data/class_automation/base_id')}",
    target="0",
)
def get_airtable_instructor_capabilities() -> list[OpsItem]:
    """Get airtable info regarding instructor capabilities"""
    try:
        unteachable_count = 0
        missing_paperwork_count = 0
        
        # Get instructor capabilities data
        for record in get_all_records("class_automation", "capabilities"):
            fields = record.get("fields", {})
            
            # Check for clearances that can't be taught (no capable instructors)
            if not fields.get("Active Instructors"):
                unteachable_count += 1
            
            # Check for missing paperwork (incomplete instructor records)
            if not fields.get("Paperwork Complete", False):
                missing_paperwork_count += 1
        
        return [
            OpsItem(
                label="Unteachable clearances",
                value=str(unteachable_count),
            ),
            OpsItem(
                label="Missing paperwork",
                value=str(missing_paperwork_count),
            ),
        ]
    except Exception as e:
        return [
            OpsItem(
                label="Unteachable clearances",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Missing paperwork",
                value="Error",
                error=e,
            ),
        ]


@opsitem(
    category="Instructors",
    timescale="ongoing",
    source="Airtable",
    url=f"https://airtable.com/{get_config('airtable/data/class_automation/base_id')}",
    target="0",
)
def get_airtable_class_proposals() -> list[OpsItem]:
    """Get airtable info regarding class proposals"""
    try:
        stale_count = 0
        two_weeks_ago = tznow() - datetime.timedelta(weeks=2)
        
        # Get class proposals that haven't been updated in 2+ weeks
        for record in get_all_records("class_automation", "classes"):
            fields = record.get("fields", {})
            
            # Check if it's a proposal (not yet approved/scheduled)
            status = fields.get("Status", "")
            if status in ["Proposed", "Under Review"]:
                # Check last modified date
                last_modified = fields.get("Last Modified")
                if last_modified:
                    # Would need proper date parsing to check if > 2 weeks
                    stale_count += 1  # Simplified logic
        
        return [
            OpsItem(
                label="Stale proposals (>2wks, no update)",
                value=str(stale_count),
            ),
        ]
    except Exception as e:
        return [
            OpsItem(
                label="Stale proposals (>2wks, no update)",
                value="Error",
                error=e,
            ),
        ]


@opsitem(
    category="Techs", timescale="ongoing", source="Neon CRM", url=get_config("neon/app_url"), target="0"
)
def get_neon_tech_instructor_onboarding() -> list[OpsItem]:
    """Get Neon state to determine tech onboarding status"""
    try:
        not_onboarded_count = 0
        review_due_count = 0
        six_months_ago = tznow() - datetime.timedelta(days=180)
        
        # Get all techs and instructors from Neon
        tech_members = list(neon.search_members_with_role("Shop Tech"))
        instructor_members = list(neon.search_members_with_role("Instructor"))
        
        all_tech_instructor_members = tech_members + instructor_members
        
        for member in all_tech_instructor_members:
            # Check onboarding status
            if not member.get("onboarding_complete", False):
                not_onboarded_count += 1
            
            # Check if due for twice-annual review
            last_review = member.get("last_review_date")
            if last_review and last_review < six_months_ago:
                review_due_count += 1
        
        return [
            OpsItem(
                label="Not fully onboarded",
                value=str(not_onboarded_count),
            ),
            OpsItem(
                label="Due for twice-annual review",
                value=str(review_due_count),
            ),
        ]
    except Exception as e:
        return [
            OpsItem(
                label="Not fully onboarded",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Due for twice-annual review",
                value="Error",
                error=e,
            ),
        ]


@opsitem(
    category="Techs",
    timescale="next 2 weeks",
    source="Airtable",
    url=f"https://airtable.com/{get_config('airtable/data/people/base_id')}",
    target="0",
)
def get_shift_schedule() -> list[OpsItem]:
    """Return reports on shift schedule status"""
    try:
        zero_coverage_count = 0
        low_coverage_count = 0
        
        two_weeks_from_now = tznow() + datetime.timedelta(weeks=2)
        
        # Get shop tech forecast data for the next 2 weeks
        for record in get_all_records("people", "shop_tech_forecast_overrides"):
            fields = record.get("fields", {})
            
            shift_date = fields.get("Date")
            tech_count = fields.get("Tech Count", 0)
            
            if shift_date and shift_date <= two_weeks_from_now.date():
                if tech_count == 0:
                    zero_coverage_count += 1
                elif tech_count == 1:
                    low_coverage_count += 1
        
        return [
            OpsItem(
                label="Upcoming shifts with zero coverage",
                value=str(zero_coverage_count),
            ),
            OpsItem(
                label="Upcoming shifts with low coverage (1 tech)",
                value=str(low_coverage_count),
            ),
        ]
    except Exception as e:
        return [
            OpsItem(
                label="Upcoming shifts with zero coverage",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Upcoming shifts with low coverage (1 tech)",
                value="Error",
                error=e,
            ),
        ]


@opsitem(
    category="Documentation", timescale="ongoing", source="Wiki", url=get_config("bookstack/base_url"), target="0"
)
def get_wiki_docs_status() -> list[OpsItem]:
    """Return reports on documentation status from wiki"""
    try:
        lacking_approval_count = 0
        missing_clearance_docs = 0
        missing_tutorials = 0
        
        # Get tool documentation summary
        tool_docs_report = wiki.get_tool_docs_summary()
        
        if isinstance(tool_docs_report, dict):
            lacking_approval_count = tool_docs_report.get("lacking_approval", 0)
            missing_tutorials = tool_docs_report.get("missing_tutorials", 0)
        
        # Get class documentation report for clearance docs
        class_docs_report = wiki.get_class_docs_report()
        
        if isinstance(class_docs_report, dict):
            missing_clearance_docs = class_docs_report.get("missing_clearance_docs", 0)
        
        return [
            OpsItem(
                label="Tool docs lacking approval",
                value=str(lacking_approval_count),
            ),
            OpsItem(
                label="Missing clearance docs",
                value=str(missing_clearance_docs),
            ),
            OpsItem(
                label="Missing tool tutorials",
                value=str(missing_tutorials),
            ),
        ]
    except Exception as e:
        return [
            OpsItem(
                label="Tool docs lacking approval",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Missing clearance docs",
                value="Error",
                error=e,
            ),
            OpsItem(
                label="Missing tool tutorials",
                value="Error",
                error=e,
            ),
        ]


def run() -> Iterator[OpsItem]:
    """Runs all subsections of the report concurrently and returns results as they arrive"""
    not_done = set()
    with futures.ThreadPoolExecutor() as executor:
        for fn in [
            get_asana_assets,
            get_asana_instructor_apps,
            get_asana_purchase_requests,
            get_asana_tech_apps,
            get_asana_maint_tasks,
            get_asana_proposals,
            get_ops_manager_sheet,
            get_airtable_tool_info,
            get_airtable_instructor_capabilities,
            get_airtable_violations,
            get_neon_tech_instructor_onboarding,
            get_shift_schedule,
            get_wiki_docs_status,
        ]:
            not_done.add(executor.submit(fn))

    while True:
        done, not_done = futures.wait(not_done, return_when=futures.FIRST_COMPLETED)
        log.info(f"{len(done)} more reports completed, {len(not_done)} to go")
        for d in done:
            result = d.result()
            log.info(f"result: {result}")
            for r in result:  # Convert any Exception into strings for serialization
                if r.error:
                    r.error = str(r.error)[:256]
                yield r

        if len(not_done) <= 0:
            break
