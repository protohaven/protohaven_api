"""Handlers for policy violations"""

import logging
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from dateutil.parser import ParserError
from flask import Blueprint, Response, request

from protohaven_api.config import get_config, safe_parse_datetime, tznow
from protohaven_api.integrations import airtable, neon_base
from protohaven_api.integrations.models import Role
from protohaven_api.rbac import require_login_role

page = Blueprint("violations", __name__)

log = logging.getLogger("handlers.violations")


def _neon_id_str(neon_id: Any) -> str | None:
    """Normalize a Neon ID from Airtable/NocoDB for display/lookup purposes."""
    if neon_id is None:
        return None
    if isinstance(neon_id, float) and neon_id.is_integer():
        return str(int(neon_id))
    return str(neon_id).strip() or None


def _linked_ids(value: Any) -> list[str]:
    """Normalize linked-record values to a list of string record IDs."""
    if not value:
        return []
    if not isinstance(value, list):
        value = [value]
    result = []
    for v in value:
        if isinstance(v, dict) and "id" in v:
            result.append(str(v["id"]))
        else:
            result.append(str(v))
    return result


def _evidence_urls(value: Any) -> list[str]:
    """Normalize evidence attachments/text into a list of URLs for the UI."""
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    result = []
    for v in value:
        if isinstance(v, dict):
            if v.get("url"):
                result.append(v["url"])
            elif v.get("path"):
                result.append(
                    f"{get_config('nocodb/requests/url')}/{str(v['path']).lstrip('/')}"
                )
        elif str(v).strip():
            result.extend(u.strip() for u in re.split(r"[\n,]", str(v)) if u.strip())
    return result


def _unpaid_fee_map(
    fees: Iterable[dict[str, Any]],
) -> defaultdict[str, float]:
    """Return a mapping of violation record ID to unpaid fee total."""
    result: defaultdict[str, float] = defaultdict(float)
    for f in fees:
        fields = f.get("fields", {})
        if fields.get("Paid"):
            continue
        vid = _linked_ids(fields.get("Violation"))
        if not vid:
            continue
        result[vid[0]] += float(fields.get("Amount") or 0)
    return result


def _violation_to_dict(
    v: dict[str, Any],
    section_map: Mapping[str, str],
    fee_map: Mapping[str, float],
) -> dict[str, Any]:
    """Convert an Airtable/NocoDB violation record into a UI-safe dict.

    Neon IDs are intentionally omitted from the response; the UI only shows the
    member's name/email after lookup.
    """
    fields = v.get("fields", {})
    neon_id = _neon_id_str(fields.get("Neon ID"))
    suspect_name = None
    suspect_email = None
    if neon_id:
        try:
            acct = neon_base.fetch_account(neon_id)
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.warning(f"Failed to look up Neon account {neon_id}: {e}")
            acct = None
        if acct:
            suspect_name = f"{acct.fname} {acct.lname}".strip() or None
            suspect_email = acct.email
    closure = fields.get("Closure")
    close_date = fields.get("Close date (from Closure)")
    if isinstance(close_date, list) and close_date:
        close_date = close_date[0]
    return {
        "id": v["id"],
        "instance": fields.get("Instance #"),
        "tag_number": fields.get("Tag Number"),
        "reporter": fields.get("Reporter"),
        "suspect_name": suspect_name,
        "suspect_email": suspect_email,
        "onset": fields.get("Onset"),
        "sections": [
            section_map.get(s, s) for s in _linked_ids(fields.get("Relevant Sections"))
        ],
        "notes": fields.get("Notes"),
        "evidence": _evidence_urls(fields.get("Evidence")),
        "daily_fee": fields.get("Daily Fee"),
        "accrued": fields.get("Accrued") or 0,
        "unpaid_fees": fee_map.get(v["id"], 0),
        "closed": bool(closure),
        "close_date": close_date,
    }


@page.route("/violations/sections")
@require_login_role(
    Role.SHOP_TECH_LEAD,
    Role.STAFF,
    Role.EDUCATION_LEAD,
    Role.SHOP_TECH,
    redirect_to_login=False,
)
def violation_sections() -> list[dict[str, Any]]:
    """Return policy sections available for a new violation."""
    return [
        {
            "id": s["id"],
            "name": s.get("fields", {}).get("Section")
            or s.get("fields", {}).get("id")
            or s["id"],
        }
        for s in airtable.get_policy_sections()
    ]


@page.route("/violations")
@require_login_role(
    Role.SHOP_TECH_LEAD,
    Role.STAFF,
    Role.EDUCATION_LEAD,
    Role.SHOP_TECH,
    redirect_to_login=False,
)
def violations() -> list[dict[str, Any]]:
    """Return open and recently closed policy violations for the techs page."""
    section_map = {
        str(s["id"]): s.get("fields", {}).get("Section") or str(s["id"])
        for s in airtable.get_policy_sections()
    }
    fee_map = _unpaid_fee_map(airtable.get_policy_fees())
    result = [
        _violation_to_dict(v, section_map, fee_map)
        for v in airtable.get_policy_violations()
    ]
    result.sort(
        key=lambda v: (
            v["closed"],
            safe_parse_datetime(v["onset"]).isoformat() if v["onset"] else "",
        )
    )
    return result


@page.route("/violations/open", methods=["POST"])
@require_login_role(
    Role.SHOP_TECH_LEAD,
    Role.STAFF,
    Role.EDUCATION_LEAD,
    Role.SHOP_TECH,
    redirect_to_login=False,
)
def open_violation() -> Response | dict[str, Any]:
    # pylint: disable=too-many-return-statements
    """Open a new violation from the techs dashboard."""
    data = request.get_json(silent=True) or {}
    reporter = (data.get("reporter") or "").strip()
    notes = (data.get("notes") or "").strip()
    sections = data.get("sections") or []
    if not reporter:
        return Response("reporter is required", status=400)
    if not notes:
        return Response("notes are required", status=400)
    if not sections:
        return Response("at least one policy section is required", status=400)
    if not data.get("onset"):
        return Response("onset is required", status=400)
    try:
        onset = safe_parse_datetime(data.get("onset"))
    except (
        TypeError,
        ValueError,
        ParserError,
    ) as e:  # pylint: disable=broad-exception-caught
        return Response(f"invalid onset: {e}", status=400)
    try:
        fee = float(data.get("daily_fee"))
    except (TypeError, ValueError) as e:
        return Response(f"invalid daily_fee: {e}", status=400)
    evidence = data.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [u.strip() for u in re.split(r"[\n,]", evidence) if u.strip()]
    violation_id = airtable.open_violation(
        reporter=reporter,
        neon_id=data.get("neon_id"),
        sections=[str(s) for s in sections],
        evidence=evidence,
        onset=onset,
        fee=fee,
        notes=notes,
        tag_number=data.get("tag_number"),
    )
    return {"ok": True, "id": violation_id}


@page.route("/violations/<violation_id>/evidence", methods=["POST"])
@require_login_role(
    Role.SHOP_TECH_LEAD,
    Role.STAFF,
    Role.EDUCATION_LEAD,
    Role.SHOP_TECH,
    redirect_to_login=False,
)
def upload_violation_evidence(violation_id: str) -> Response | dict[str, Any]:
    """Upload one or more pictures to a violation's Evidence field."""
    files = request.files.getlist("files")
    if not files:
        return Response("at least one file is required", status=400)
    if any(not (f.mimetype or "").startswith("image/") for f in files):
        return Response("only image files are supported", status=400)
    airtable.upload_violation_evidence(
        violation_id,
        [
            (f.filename or "upload", f.mimetype or "application/octet-stream", f.read())
            for f in files
        ],
    )
    return {"ok": True}


@page.route("/violations/<violation_id>/close", methods=["POST"])
@require_login_role(
    Role.SHOP_TECH_LEAD,
    Role.STAFF,
    Role.EDUCATION_LEAD,
    Role.SHOP_TECH,
    redirect_to_login=False,
)
def close_violation(violation_id: str) -> Response | dict[str, bool]:
    """Close out a violation by creating a closure record."""
    data = request.get_json(silent=True) or {}
    closer = (data.get("closer") or "").strip()
    if not closer:
        return Response("closer is required", status=400)
    try:
        close_date = safe_parse_datetime(data.get("close_date") or tznow().isoformat())
    except (
        TypeError,
        ValueError,
        ParserError,
    ) as e:  # pylint: disable=broad-exception-caught
        return Response(f"invalid close_date: {e}", status=400)
    airtable.close_violation(
        violation_id,
        closer=closer,
        resolution=close_date,
        notes=(data.get("notes") or "").strip(),
        fees_outstanding=bool(data.get("fees_outstanding")),
    )
    return {"ok": True}
