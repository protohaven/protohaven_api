"""Airtable basic API commands"""

import logging
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

from protohaven_api.integrations.data.connector import get as get_connector

log = logging.getLogger("integrations.airtable_base")


class TableNotFoundError(Exception):
    """Error for table not found"""


def _idref(rec: dict[str, Any], field: str) -> list[str]:
    """There's a difference in referencing IDs of linked fields in Airtable vs NocoDB.
    This helper normalizes both and handles the null case"""
    vv = rec["fields"].get(field)
    if vv is None:
        return []
    if isinstance(vv, dict) and "id" in vv:
        return [str(vv["id"])]
    if not isinstance(vv, list):
        raise RuntimeError(
            f"Invalid linked field data encountered for field {field}: {vv}\n"
            "Check if field is LTAR for NocodB "
            "(https://github.com/nocodb/nocodb/issues/12717#issuecomment-3739524647)"
        )
    if len(vv) > 0 and isinstance(vv[0], dict):
        return [str(v["id"]) for v in vv]
    return vv


def _refid(id_ref: str) -> dict[str, int] | str:
    """Use the correct Airtable/Nocodb format when inserting records with linked fields"""
    if get_connector().db_format() == "nocodb":
        return {"id": int(id_ref)}
    return id_ref


def get_record(base, tbl, rec):
    """Grabs a record from a named table (from config.yaml)"""
    status, content = get_connector().db_request("GET", base, tbl, rec)
    if status != 200:
        raise RuntimeError(f"Airtable fetch {base} {tbl} {rec}", status, content)
    return content


MAX_ITERS = 100


def get_all_records(
    base: str, tbl: str, params: dict = None
) -> Iterable[dict[str, Any]]:
    """Get all records for a given named table (ID in config.yaml)"""
    records: list[dict[str, Any]] = []
    s = ""
    params = params or {}
    niter = 0
    while niter < MAX_ITERS:
        status, content = get_connector().db_request("GET", base, tbl, params=params)
        if status == 404:
            raise TableNotFoundError(
                f"Airtable fetch {base} {tbl} {s}",
                status,
                content,
            )
        if status != 200:
            raise RuntimeError(
                f"Airtable fetch {base} {tbl} {s}",
                status,
                content,
            )
        data = content
        if get_connector().db_format() == "nocodb":
            records += data["records"]
            if not "next" in data:
                break
            log.info(data["next"])

            parsed = parse_qs(urlparse(data["next"]).query)
            params["page"] = parsed["page"][0]
            if "pageSize" in parsed:
                params["pageSize"] = parsed["pageSize"][0]
        else:
            records += data["records"]
            if data.get("offset") is None:
                break
            params["offset"] = data["offset"]
        niter += 1
    return records


def get_all_records_between(base, tbl, start_date, end_date, field="Created"):
    """Returns a list of all records in the table with the
    Created field timestamp after a certain date"""
    params = {}
    if not end_date:
        return get_all_records_after(base, tbl, start_date, field)

    if get_connector().db_format() == "nocodb":
        params["where"] = (
            f"({field},le,exactDate,{end_date.isoformat()})~and({field},ge,exactDate,{start_date.isoformat()})"  # pylint: disable=line-too-long
        )
    else:
        params["filterByFormula"] = (
            f"AND(IS_BEFORE({{{field}}}, '{end_date.isoformat()}'), IS_AFTER({{{field}}},'{start_date.isoformat()}'))"  # pylint: disable=line-too-long
        )

    return get_all_records(base, tbl, params)


def get_all_records_after(base, tbl, after_date, field="Created"):
    """Returns a list of all records in the table with the
    Created field timestamp after a certain date"""
    params = {}
    if get_connector().db_format() == "nocodb":
        params["where"] = f"({field},ge,exactDate,{after_date.isoformat()})"
    else:
        params["filterByFormula"] = f"IS_AFTER({{{field}}},'{after_date.isoformat()}')"

    return get_all_records(base, tbl, params)


def insert_records(records, base, tbl):
    """Inserts one or more records into a named table. the "fields" structure is
    automatically applied.
    """
    # Max of 10 records allowed for insertion, see
    # https://airtable.com/developers/web/api/create-records
    assert len(records) <= 10

    post_data = [{"fields": d} for d in records]
    if get_connector().db_format() != "nocodb":
        post_data = {"records": post_data}
    return get_connector().db_request("POST", base, tbl, data=post_data)


def update_record(data, base, tbl, rec):
    """Updates/patches a record in a named table.
    Note that this uses an API endpoint that supports multiple records,
    up to a max of 10. We could modify this to better batch data requests in the future.
    """
    post_data = [{"id": rec, "fields": data}]
    if get_connector().db_format() != "nocodb":
        post_data = {"records": post_data}

    result = get_connector().db_request("PATCH", base, tbl, data=post_data)
    if get_connector().db_format() != "nocodb":
        return result

    # Nocodb doesn't return the rest of the object on an update, so we have to
    # do it in a separate request to match Airtable.
    # We rely on get_record's error handling and just pass 200 here
    return 200, get_record(base, tbl, rec)


def delete_record(base, tbl, rec):
    """Deletes a record in a named table.
    Note that this uses a NocoDB API endpoint that supports multiple records,
    up to a max of 10. We could modify this to better batch data requests in the future.
    """
    if get_connector().db_format() == "nocodb":
        return get_connector().db_request("DELETE", base, tbl, data=[{"id": rec}])
    return get_connector().db_request("DELETE", base, tbl, rec=rec)
