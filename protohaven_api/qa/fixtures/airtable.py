"""Airtable QA fixture helpers."""

from typing import Any

from protohaven_api.integrations import airtable, airtable_base
from protohaven_api.qa.base import QAContext


def _record_ids(content: Any) -> list[str]:
    if isinstance(content, dict) and "records" in content:
        return [r["id"] for r in content["records"]]
    if isinstance(content, (list, tuple)):
        return [
            r.get("id") or r.get("Id")
            for r in content
            if isinstance(r, dict)
        ]
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
    _, content = airtable_base.insert_records([fields], base, table)
    rec_id = _record_ids(content)[0]
    ctx.cleanup.register(
        f"delete Airtable {base}/{table} record {rec_id} ({description})",
        lambda: airtable_base.delete_record(base, table, rec_id),
    )
    return rec_id


def create_signin(
    ctx: QAContext, email: str, created: str, full_name: str
) -> str:
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
    _, content = airtable.append_classes_to_schedule([payload])
    rec_id = _record_ids(content)[0]
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
    ctx: QAContext, neon_id: str, tool_code: str, deadline: str
) -> str:
    """Create a pending recertification row."""
    from protohaven_api.config import safe_parse_datetime

    parsed_deadline = safe_parse_datetime(deadline)
    _, content = airtable.insert_pending_recertification(
        neon_id, tool_code, parsed_deadline, parsed_deadline
    )
    rec_id = _record_ids(content)[0]
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


def get_all_records(base: str, table: str):
    """Thin passthrough for snapshot/diff logic."""
    return list(airtable_base.get_all_records(base, table))
