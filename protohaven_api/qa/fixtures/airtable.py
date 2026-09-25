"""Airtable QA fixture helpers."""

# pylint: disable=too-many-arguments

from typing import Any

from protohaven_api.config import safe_parse_datetime, tznow
from protohaven_api.integrations import airtable, airtable_base
from protohaven_api.qa.base import QAContext


def _record_ids(content: Any) -> list[str]:
    if isinstance(content, dict) and "records" in content:
        return [r["id"] for r in content["records"]]
    if isinstance(content, (list, tuple)):
        return [r.get("id") or r.get("Id") for r in content if isinstance(r, dict)]
    return []


def insert_record(
    ctx: QAContext,
    base: str,
    table: str,
    fields: dict[str, Any],
    *,
    description: str,
) -> str:
    """Insert one record and register its deletion."""
    status, content = airtable_base.insert_records([fields], base, table)
    ids = _record_ids(content)
    if status != 200 or not ids:
        raise RuntimeError(f"Insert {base}/{table} failed: {status} {content}")
    rec_id = ids[0]
    ctx.cleanup.register(
        f"delete Airtable {base}/{table} record {rec_id} ({description})",
        lambda: airtable_base.delete_record(base, table, rec_id),
    )
    return rec_id


def create_signin(ctx: QAContext, email: str, created: str, full_name: str) -> str:
    """Create a front-desk sign-in record."""
    return insert_record(
        ctx,
        "people",
        "sign_ins",
        {"Email": email, "Created": created, "Full Name": full_name},
        description="tech sign-in",
    )


def create_schedule_row(ctx: QAContext, payload: dict[str, Any]) -> str:
    """Create a class schedule row and register its deletion."""
    status, content = airtable.append_classes_to_schedule([payload])
    ids = _record_ids(content)
    if status != 200 or not ids:
        raise RuntimeError(
            f"Insert class_automation/schedule failed: {status} {content}"
        )
    rec_id = ids[0]
    ctx.cleanup.register(
        f"delete class_automation/schedule record {rec_id}",
        lambda: airtable_base.delete_record("class_automation", "schedule", rec_id),
    )
    return rec_id


def create_capabilities_row(ctx: QAContext, fields: dict[str, Any]) -> str:
    """Create an instructor capabilities row."""
    return insert_record(
        ctx,
        "class_automation",
        "capabilities",
        fields,
        description="instructor capability",
    )


def create_pending_recert(
    ctx: QAContext,
    neon_id: str,
    tool_code: str,
    deadline: str,
    *,
    notified: bool = True,
    suspended: bool = False,
) -> str:
    """Create a pending recertification row."""
    parsed_deadline = safe_parse_datetime(deadline)
    _, content = airtable.insert_pending_recertification(
        neon_id, tool_code, parsed_deadline, parsed_deadline
    )
    rec_id = _record_ids(content)[0]
    airtable.update_pending_recertification(
        rec_id,
        suspended=suspended,
    )
    if notified:
        airtable.update_record(
            {"Notified": tznow().isoformat()},
            "people",
            "recertification",
            rec_id,
        )
    ctx.cleanup.register(
        f"remove pending recertification {rec_id}",
        lambda: airtable.remove_pending_recertification(rec_id),
    )
    return rec_id


def create_coupon_record(
    ctx: QAContext, code: str, amount: int, use_by: str, expires: str
) -> str:
    """Create an Airtable coupon record."""
    return insert_record(
        ctx,
        "class_automation",
        "discounts",
        {"Code": code, "Amount": amount, "Use By": use_by, "Expires": expires},
        description="coupon",
    )


def create_empty_shift_override(
    ctx: QAContext,
    date,
    ap: str,
    original_tech_names: list[str],
) -> str:
    """Force a forecast shift to be empty and register cleanup.

    If the shift already has an override, replace it with an empty legacy
    override and restore the original override during cleanup instead of
    layering a second record on top of it.
    """
    shift_key = f"{safe_parse_datetime(date).strftime('%Y-%m-%d')} {ap}"
    existing_id = None
    for key, (rec_id, _, _) in airtable.get_forecast_overrides(include_pii=True):
        if key == shift_key:
            existing_id = rec_id
            break

    if existing_id is not None:
        original = airtable_base.get_record(
            "people", "shop_tech_forecast_overrides", existing_id
        )
        original_fields = dict(original.get("fields", {}))
        airtable_base.update_record(
            {"Override": ""},
            "people",
            "shop_tech_forecast_overrides",
            existing_id,
        )
        ctx.cleanup.register(
            f"restore shop_tech_forecast_overrides {existing_id}",
            lambda: airtable_base.update_record(
                original_fields,
                "people",
                "shop_tech_forecast_overrides",
                existing_id,
            ),
        )
        return existing_id

    _, content = airtable.set_forecast_override(
        None,
        date,
        ap,
        [],
        original_tech_names,
        ctx.run_id,
        "Cronicle QA",
    )
    rec_id = _record_ids(content)[0]
    ctx.cleanup.register(
        f"delete shop_tech_forecast_overrides {rec_id}",
        lambda: airtable.delete_forecast_override(rec_id),
    )
    return rec_id


def create_violation(
    ctx: QAContext,
    neon_id: str,
    *,
    daily_fee: int = 5,
    onset=None,
    notes: str = "QA Cronicle policy violation",
) -> str:
    """Create a temporary policy violation linked to a mock Neon account."""
    sections = airtable.get_policy_sections()
    assert sections, "No policy sections configured"
    section = sections[0]
    _, content = airtable_base.insert_records(
        [
            {
                "Neon ID": neon_id,
                "Onset": (onset or tznow()).isoformat(),
                "Daily Fee": daily_fee,
                "Notes": notes,
                "Relevant Sections": [section["id"]],
            }
        ],
        "policy_enforcement",
        "violations",
    )
    rec_id = _record_ids(content)[0]
    ctx.cleanup.register(
        f"delete policy_enforcement/violations record {rec_id}",
        lambda: airtable_base.delete_record("policy_enforcement", "violations", rec_id),
    )
    return rec_id


def create_tool_record(
    ctx: QAContext,
    *,
    tool_code: str,
    tool_name: str,
    area: str,
    booked_resource_id: Any,
    reservable: bool = True,
) -> str:
    """Create a temporary Airtable tool record tied to a mock Booked resource."""
    return insert_record(
        ctx,
        "tools_and_equipment",
        "tools",
        {
            "Tool Code": tool_code,
            "Tool Name": tool_name,
            "Name (from Shop Area)": [area],
            "BookedResourceId": booked_resource_id,
            "Reservable": reservable,
            "Current Status": "Green",
        },
        description="tool",
    )


def get_all_records(base: str, table: str):
    """Thin passthrough for snapshot/diff logic."""
    return list(airtable_base.get_all_records(base, table))
