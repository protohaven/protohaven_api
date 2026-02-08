"""This module fetches from a wide range of primary data sources to create a comprehensive report
on the operational state of the shop."""

import datetime
import logging
import traceback
from concurrent import futures
from dataclasses import asdict, dataclass
from typing import Callable, Iterator

from protohaven_api.automation.techs import techs as tauto
from protohaven_api.config import get_config, safe_parse_datetime, tznow
from protohaven_api.handlers.instructor import get_instructor_readiness
from protohaven_api.integrations import neon, sheets, tasks, wiki
from protohaven_api.integrations.airtable_base import get_all_records
from protohaven_api.integrations.models import Role

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

    # Used for displaying status as things load
    index: int = 0
    total: int = 0


def _handle_exc(e, labels):
    traceback.print_exc()
    return [
        OpsItem(
            label=label,
            value="Error",
            error=e,
        )
        for label in labels
    ]


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


@opsitem(
    category="Financial",
    timescale="last 12 months",
    source="Asana",
    url="https://app.asana.com",
    target="0",
)
def get_asana_assets() -> list[OpsItem]:
    """Return metrics for asset listing and sale from Asana"""
    try:
        unlisted_count = 0
        unsold_count = 0
        for a in tasks.get_asset_disposal(exclude_complete=True):
            if "unlisted" in a["sections"]:
                unlisted_count += 1
            if "listed" in a["sections"]:
                unsold_count += 1
        return [
            OpsItem(label="Unlisted assets", value=str(unlisted_count)),
            OpsItem(label="Unsold listings", value=str(unsold_count)),
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(e, ["Unlisted assets", "Unsold listings"])


@opsitem(
    category="Instructor",
    timescale="ongoing",
    source="Asana",
    url=f"https://app.asana.com/0/{get_config('asana/instructor_applicants/gid')}/board",
    target="0",
)
def get_asana_instructor_apps() -> list[OpsItem]:
    """Return metrics for instructor applications from asana"""
    try:
        two_weeks_ago = tznow() - datetime.timedelta(weeks=2)
        stalled_count = 0
        for app in tasks.get_instructor_applicants(
            exclude_on_hold=True, exclude_complete=True
        ):
            if app["modified_at"] < two_weeks_ago:
                stalled_count += 1

        return [
            OpsItem(
                label="Stalled applications (>2wks)",
                value=str(stalled_count),
            )
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(e, ["Stalled applications (>2wks)"])


@opsitem(
    category="Techs",
    timescale="ongoing",
    source="Asana",
    url=f"https://app.asana.com/0/{get_config('asana/shop_and_maintenance_tasks/gid')}/board",
    target="0",
)
def get_asana_maint_tasks() -> list[OpsItem]:
    """Return metrics for maintenance tasks from asana"""
    try:
        two_weeks_ago = tznow() - datetime.timedelta(weeks=2)
        on_hold_count = 0
        stale_count = 0

        for _, modified_at, section in tasks.get_tech_ready_tasks(tznow()):
            if modified_at and modified_at < two_weeks_ago:
                stale_count += 1
            if section == "on_hold":
                on_hold_count += 1

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
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(
            e,
            [
                "On hold maintenance tasks",
                "Stale maintenance tasks (>2wks, no updates)",
            ],
        )


@opsitem(
    category="Projects",
    timescale="ongoing",
    source="Asana",
    url=f"https://app.asana.com/0/{get_config('asana/project_tracker/gid')}/board",
    target="0",
)
def get_asana_proposals() -> list[OpsItem]:
    """Return metrics for project proposals/approvals from asana"""
    try:
        on_hold_count = 0
        stale_count = 0
        two_weeks_ago = tznow() - datetime.timedelta(days=14)

        # Get project requests from Asana
        for _, section, _, modified in tasks.get_project_tracker(
            include_complete=False
        ):
            if section == "on_hold":
                on_hold_count += 1
            elif modified < two_weeks_ago:
                stale_count += 1

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
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(e, ["On hold", "Stale status (>2wks, no updates)"])


@opsitem(
    category="Tech",
    timescale="ongoing",
    source="Asana",
    url=f"https://app.asana.com/0/{get_config('asana/shop_tech_applicants/gid')}/board",
    target="0",
)
def get_asana_tech_apps() -> list[OpsItem]:
    """Return metrics for tech applications from asana"""
    try:
        stalled_count = 0
        two_weeks_ago = tznow() - datetime.timedelta(days=14)
        # Get tech applications that are not on hold and not completed
        for req in tasks.get_shop_tech_applicants(
            exclude_on_hold=True, exclude_complete=True
        ):
            if req["modified_at"] <= two_weeks_ago:
                stalled_count += 1

        return [
            OpsItem(
                label="Stalled applications (>2wks)",
                value=str(stalled_count),
            )
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(e, ["Stalled applications (>2wks)"])


@opsitem(
    category="Inventory",
    timescale="ongoing",
    source="Asana",
    url=f"https://app.asana.com/0/{get_config('asana/purchase_requests/gid')}/board",
    target="0",
)
def get_asana_purchase_requests() -> list[OpsItem]:
    """Return metrics for purchase requests from asana"""
    try:
        on_hold_count = 0
        stale_count = 0
        two_weeks_ago = tznow() - datetime.timedelta(weeks=2)

        for pr in tasks.get_purchase_requests(exclude_complete=True):
            log.info(str(pr))
            if "on_hold" in pr["sections"]:
                on_hold_count += 1
            if pr["modified_at"] < two_weeks_ago:
                stale_count += 1

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
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(
            e,
            [
                "Purchase requests on hold",
                "Purchase requests w/ no update (>2wks)",
            ],
        )


@opsitem(
    category="Inventory",
    source="Sheet",
    url=f"https://docs.google.com/spreadsheets/d/{get_config('sheets/ids/shop_manager_logbook')}",
    timescale="ongoing",
    target="0",
)
def get_ops_manager_sheet_inventory() -> list[OpsItem]:
    """Return metrics from ops manager spreadsheet"""
    try:
        items = list(sheets.get_ops_inventory())
        low_stock = sum(
            1 for item in items if 0 < item["Recorded Qty"] < item["Target Qty"]
        )
        no_stock = sum(1 for item in items if item["Recorded Qty"] <= 0)
        return [
            OpsItem(
                label="Low stock",
                value=str(low_stock),
                color="warning" if low_stock > 0 else None,
            ),
            OpsItem(
                label="Out of stock",
                value=str(no_stock),
                color="warning" if no_stock > 0 else None,
            ),
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(e, ["Low Stock", "Out of Stock"])


@opsitem(
    source="Sheet",
    url=f"https://docs.google.com/spreadsheets/d/{get_config('sheets/ids/shop_manager_logbook')}",
    timescale="ongoing",
    target="0",
)
def get_ops_manager_sheet_events() -> list[OpsItem]:
    """Return metrics from ops manager spreadsheet"""
    try:
        most_recent: dict[str, datetime.datetime] = {}
        for evt in sheets.get_ops_event_log():
            typ = evt["Type"]
            if typ not in most_recent or most_recent[typ] < evt["Date"]:
                most_recent[typ] = evt["Date"]
        intervals = {
            "Respirator QFT": ("Safety", "Days until respirator QFT req'd", 365),
            "HazCom": ("Safety", "Days until HazCom req'd", 365),
            "Tech Safety": (
                "Safety",
                "Days until volunteer safety training req'd",
                365,
            ),
            "Full Inventory": ("Inventory", "Days until full inventory req'd", 30),
            "SDS Review": ("Safety", "Days until full SDS review req'd", 365),
        }
        results = []
        now = tznow()
        for k, vv in intervals.items():
            category, label, interval = vv
            nxt = now
            if k in most_recent:
                nxt = most_recent[k] + datetime.timedelta(days=interval)
            results.append(
                OpsItem(
                    category=category,
                    label=label,
                    value=str((nxt - now).days),
                    target=">0",
                    color="warning" if nxt <= now else None,
                )
            )
        return results
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(
            e,
            [
                "Days until respirator QFT req'd",
                "Days until HazCom req'd",
                "Days until volunteer safety training req'd",
                "Days until full inventory req'd",
                "Days until full SDS review req'd",
            ],
        )


@opsitem(
    category="Financial",
    source="Sheet",
    url=f"https://docs.google.com/spreadsheets/d/{get_config('sheets/ids/shop_manager_logbook')}",
    timescale="ongoing",
    target="0",
)
def get_ops_manager_sheet_budget() -> list[OpsItem]:
    """Return metrics from ops manager spreadsheet"""
    try:
        current_year = tznow().year
        budget = sheets.get_ops_budget_state()
        return [
            OpsItem(
                timescale="30 days",
                label="Spend rate",
                value=f"${budget['30 day spend rate']}",
                target=f"<${budget['monthly budget']}",
                color=(
                    "warning"
                    if budget["30 day spend rate"] > budget["monthly budget"]
                    else None
                ),
            ),
            OpsItem(
                timescale=str(current_year),
                label="Annual budget spend",
                value=f"${budget['annual expenses']}",
                target=f"<${budget['annual budget']}",
                color=(
                    "warning"
                    if budget["annual expenses"] > budget["annual budget"]
                    else None
                ),
            ),
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(e, ["Spend rate", "Annual budget spend"])


@opsitem(
    category="Inventory",
    timescale="ongoing",
    source="Airtable",
    url=f"https://airtable.com/{get_config('airtable/data/policy_enforcement/base_id')}",
    target="0",
)
def get_airtable_violations() -> list[OpsItem]:
    """Return report info about storage and other violations from Airtable"""
    try:
        open_count = 0
        stale_count = 0
        one_week_ago = tznow() - datetime.timedelta(weeks=1)
        for record in get_all_records("policy_enforcement", "violations"):
            fields = record.get("fields", {})
            if not fields.get("Closure"):
                open_count += 1
                onset = fields.get("Onset")
                if onset and safe_parse_datetime(onset) < one_week_ago:
                    stale_count += 1  # Simplified logic

        return [
            OpsItem(
                label="Open violations",
                value=str(open_count),
                color="warning" if open_count > 0 else None,
            ),
            OpsItem(
                label="Open and stale violations (>1wk)",
                value=str(stale_count),
                color="warning" if stale_count > 0 else None,
            ),
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(e, ["Open violations", "Open and stale violations (>1wk)"])


@opsitem(
    category="Equipment",
    timescale="ongoing",
    source="Airtable",
    url=f"https://airtable.com/{get_config('airtable/data/tools_and_equipment/base_id')}",
    target="0",
)
def get_airtable_tool_info() -> list[OpsItem]:
    """Return report info about the state of tools in Airtable"""
    try:
        red_tagged_count = 0
        yellow_tagged_count = 0
        blue_tagged_count = 0

        seven_days_ago = tznow() - datetime.timedelta(days=7)
        fourteen_days_ago = tznow() - datetime.timedelta(days=14)

        # Get all tools and their status
        for record in get_all_records("tools_and_equipment", "tools"):
            fields = record.get("fields", {})
            tag_status = (fields.get("Current Status") or "").split(" ")[0]
            tag_date = fields.get("Status last modified")
            if not tag_status or not tag_date:
                continue
            tag_date = safe_parse_datetime(tag_date)

            if tag_status == "Red" and tag_date < seven_days_ago:
                # Would need proper date parsing to check if > 7 days
                red_tagged_count += 1
            elif tag_status == "Yellow" and tag_date < fourteen_days_ago:
                # Would need proper date parsing to check if > 14 days
                yellow_tagged_count += 1
            elif tag_status == "Blue":
                blue_tagged_count += 1

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
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(
            e,
            [
                "Red tagged >7d",
                "Yellow tagged >14d",
                "Blue tagged",
                "Physical/digital tag mismatches corrected",
            ],
        )


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
        all_codes = {
            r["fields"]["Code"]
            for r in get_all_records("class_automation", "clearance_codes")
        }
        log.info(f"All codes: {all_codes}")
        teachable_codes = set()
        for record in get_all_records("class_automation", "capabilities"):
            fields = record.get("fields", {})

            # Check for clearances that can't be taught (no capable instructors)
            for code in fields.get("Code (from Private Instruction)") or []:
                teachable_codes.add(code)

            # Check for missing paperwork (not including visibility on main page)
            if not fields.get("W9 Form") or not fields.get("Direct Deposit Info"):
                missing_paperwork_count += 1

        log.info(f"Teachable codes: {teachable_codes}")
        unteachable_count = len(all_codes - teachable_codes)

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
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(e, ["Unteachable clearances", "Missing paperwork"])


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
        proposed_count = 0
        for record in get_all_records("class_automation", "class_templates"):
            fields = record.get("fields", {})
            if not fields.get("Approved") and not fields.get("Discontinued"):
                proposed_count += 1
        return [
            OpsItem(
                label="Unresolved class proposals",
                value=str(proposed_count),
            ),
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(e, ["Unresolved class proposals"])


@opsitem(
    category="Instructor/Tech",
    timescale="ongoing",
    source="Neon CRM",
    url=get_config("neon/app_url"),
    target="0",
)
def get_neon_tech_instructor_onboarding() -> list[OpsItem]:
    """Get Neon state to determine tech onboarding status"""
    try:
        not_onboarded_count = 0
        review_due_count = 0
        six_months_ago = tznow() - datetime.timedelta(days=180)

        # Get all techs and instructors from Neon
        for m in list(
            neon.search_members_with_role(
                Role.SHOP_TECH, fields=[neon.CustomField.LAST_REVIEW]
            )
        ):
            lr = m.last_review
            if not lr or lr < six_months_ago:
                review_due_count += 1

        for m in list(neon.search_members_with_role(Role.INSTRUCTOR)):
            readiness = get_instructor_readiness([m])
            for v in readiness.values():
                if v != "OK":
                    not_onboarded_count += 1
                    break

        return [
            OpsItem(
                category="Instructors",
                label="Not fully onboarded",
                value=str(not_onboarded_count),
            ),
            OpsItem(
                category="Techs",
                label="Due for twice-annual review",
                value=str(review_due_count),
            ),
        ]
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(e, ["Not fully onboarded", "Due for twice-annual review"])


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
        for day in tauto.generate(tznow(), 14)["calendar_view"]:
            if day["is_holiday"]:
                continue
            for shift in ("AM", "PM"):
                if len(day[shift]["people"]) <= 0:
                    zero_coverage_count += 1
                elif len(day[shift]["people"]) <= 1:
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
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(
            e,
            [
                "Upcoming shifts with zero coverage",
                "Upcoming shifts with low coverage (1 tech)",
            ],
        )


@opsitem(
    category="Documentation",
    timescale="ongoing",
    source="Wiki",
    url=get_config("bookstack/base_url"),
    target="0",
)
def get_wiki_docs_status() -> list[OpsItem]:
    """Return reports on documentation status from wiki"""
    try:
        lacking_approval_count = 0
        missing_clearance_docs = 0
        missing_tutorials = 0

        # Get tool documentation summary
        for _, report in wiki.get_tool_docs_summary()["by_code"].items():
            clr = report.get("clearance") or []
            tut = report.get("tool_tutorial") or []
            if len(tut) <= 0:
                missing_tutorials += 1
            if len(clr) <= 0:
                missing_clearance_docs += 1
            for doc in clr + tut:
                if not doc.get("approved_revision"):
                    lacking_approval_count += 1

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
    except Exception as e:  # pylint: disable=broad-exception-caught
        return _handle_exc(
            e,
            [
                "Tool docs lacking approval",
                "Missing clearance docs",
                "Missing tool tutorials",
            ],
        )


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
            get_ops_manager_sheet_budget,
            get_ops_manager_sheet_events,
            get_ops_manager_sheet_inventory,
            get_airtable_tool_info,
            get_airtable_instructor_capabilities,
            get_airtable_violations,
            get_neon_tech_instructor_onboarding,
            get_shift_schedule,
            get_wiki_docs_status,
        ]:
            not_done.add(executor.submit(fn))

    total = len(not_done)
    while True:
        done, not_done = futures.wait(not_done, return_when=futures.FIRST_COMPLETED)
        log.info(f"{len(done)} more reports completed, {len(not_done)} to go")
        for d in done:
            result = d.result()
            log.info(f"result: {result}")
            for r in result:  # Convert any Exception into strings for serialization
                if r.error:
                    r.error = str(r.error)[:256]
                r.total = total
                r.index = total - len(not_done)
                yield r

        if len(not_done) <= 0:
            break
