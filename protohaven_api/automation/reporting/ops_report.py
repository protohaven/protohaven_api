"""This module fetches from a wide range of primary data sources to create a comprehensive report
on the operational state of the shop."""

import logging
from concurrent import futures
from dataclasses import asdict, dataclass
from typing import Callable, Iterator

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


@opsitem(category="Financial", timescale="last 12 months", source="Asana", url="TODO")
def get_asana_assets() -> list[OpsItem]:
    """Return metrics for asset listing and sale from Asana"""
    return [
        OpsItem(label="Unlisted assets", value="X", target="0"),
        OpsItem(label="Unsold listings", value="Y", target="0"),
    ]


@opsitem(
    category="Instructor", timescale="ongoing", source="Asana", url="TODO", target="0"
)
def get_asana_instructor_apps() -> list[OpsItem]:
    """Return metrics for instructor applications from asana"""
    return [
        OpsItem(
            label="Stalled applications (>2wks)",
            value="X",
        )
    ]


@opsitem(category="Techs", timescale="ongoing", source="Asana", url="TODO", target="0")
def get_asana_maint_tasks() -> list[OpsItem]:
    """Return metrics for maintenance tasks from asana"""
    return [
        OpsItem(
            label="On hold maintenance tasks",
            value="X",
        ),
        OpsItem(
            label="Stale maintenance tasks (>2wks, no updates)",
            value="X",
        ),
    ]


@opsitem(
    category="Projects", timescale="ongoing", source="Asana", url="TODO", target="0"
)
def get_asana_proposals() -> list[OpsItem]:
    """Return metrics for project proposals/approvals from asana"""
    return [
        OpsItem(
            label="On hold",
            value="X",
        ),
        OpsItem(
            label="Stale status (>2wks, no updates)",
            value="X",
        ),
    ]


@opsitem(category="Tech", timescale="ongoing", source="Asana", url="TODO", target="0")
def get_asana_tech_apps() -> list[OpsItem]:
    """Return metrics for tech applications from asana"""
    return [
        OpsItem(
            label="Stalled applications (>2wks)",
            value="X",
        )
    ]


@opsitem(
    category="Inventory", timescale="ongoing", source="Asana", url="TODO", target="0"
)
def get_asana_purchase_requests() -> list[OpsItem]:
    """Return metrics for purchase requests from asana"""
    return [
        OpsItem(
            label="Purchase requests on hold",
            value="X",
        ),
        OpsItem(
            label="Purchase requests w/ no update (>2wks)",
            value="X",
        ),
    ]


@opsitem(source="Sheet", url="TODO", timescale="ongoing", target="0")
def get_ops_manager_sheet() -> list[OpsItem]:
    """Return metrics from ops manager spreadsheet"""
    return [
        OpsItem(
            category="Financial",
            timescale="YYYY",
            label="Spend rate",
            value="$X",
            target="<$Y",
            color="warning",
        ),
        OpsItem(
            category="Safety",
            label="Days until volunteer safety training req'd",
            value="X",
            target=">0",
        ),
        OpsItem(
            category="Safety",
            label="Days until HazCom / QFT req'd",
            value="X",
            target=">0",
        ),
        OpsItem(
            category="Safety",
            label="Days until full SDS review req'd",
            value="X",
            target=">0",
        ),
        OpsItem(
            category="Inventory",
            label="Low stock",
            value="X",
        ),
        OpsItem(
            category="Inventory",
            label="Out of stock",
            value="X",
        ),
        OpsItem(
            category="Inventory",
            label="Days until next full inventory req'd",
            value="X",
            target=">0",
        ),
    ]


@opsitem(
    category="Inventory", timescale="ongoing", source="Airtable", url="TODO", target="0"
)
def get_airtable_violations() -> list[OpsItem]:
    """Return report info about storage and other violations from Airtable"""
    return [
        OpsItem(
            label="Open violations",
            value="X",
        ),
        OpsItem(
            label="Open and stale violations (>1wk)",
            value="X",
        ),
    ]


@opsitem(
    category="Equipment", timescale="ongoing", source="Airtable", url="TODO", target="0"
)
def get_airtable_tool_info() -> list[OpsItem]:
    """Return report info about the state of tools in Airtable"""
    return [
        OpsItem(
            label="Red tagged >7d",
            value="X",
        ),
        OpsItem(
            label="Yellow tagged >14d",
            value="X",
        ),
        OpsItem(
            label="Blue tagged",
            value="X",
        ),
        OpsItem(
            label="Physical/digital tag mismatches corrected",
            value="X",
            timescale="last 14 days",
        ),
    ]


@opsitem(
    category="Instructors",
    timescale="ongoing",
    source="Airtable",
    url="TODO",
    target="0",
)
def get_airtable_instructor_capabilities() -> list[OpsItem]:
    """Get airtable info regarding instructor capabilities"""
    return [
        OpsItem(
            label="Unteachable clearances",
            value="X",
        ),
        OpsItem(
            label="Missing paperwork",
            value="X",
        ),
    ]


@opsitem(
    category="Instructors",
    timescale="ongoing",
    source="Airtable",
    url="TODO",
    target="0",
)
def get_airtable_class_proposals() -> list[OpsItem]:
    """Get airtable info regarding class proposals"""
    return [
        OpsItem(
            label="Stale proposals (>2wks, no update)",
            value="X",
        ),
    ]


@opsitem(
    category="Techs", timescale="ongoing", source="Neon CRM", url="TODO", target="0"
)
def get_neon_tech_instructor_onboarding() -> list[OpsItem]:
    """Get Neon state to determine tech onboarding status"""
    return [
        OpsItem(
            label="Not fully onboarded",
            value="X",
        ),
        OpsItem(
            label="Due for twice-annual review",
            value="X",
        ),
    ]


@opsitem(
    category="Techs",
    timescale="next 2 weeks",
    source="Airtable",
    url="TODO",
    target="0",
)
def get_shift_schedule() -> list[OpsItem]:
    """Return reports on shift schedule status"""
    return [
        OpsItem(
            label="Upcoming shifts with zero coverage",
            value="X",
        ),
        OpsItem(
            label="Upcoming shifts with low coverage (1 tech)",
            value="X",
        ),
    ]


@opsitem(
    category="Documentation", timescale="ongoing", source="Wiki", url="TODO", target="0"
)
def get_wiki_docs_status() -> list[OpsItem]:
    """Return reports on shift schedule status"""
    return [
        OpsItem(
            label="Tool docs lacking approval",
            value="X",
            error=RuntimeError(
                "This is a test exception with a long and detailed summary of state"
            ),
        ),
        OpsItem(
            label="Missing clearance docs",
            value="X",
        ),
        OpsItem(
            label="Missing tool tutorials",
            value="X",
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
