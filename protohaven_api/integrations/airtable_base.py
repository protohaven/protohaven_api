"""Airtable basic API commands"""

import logging

from protohaven_api.integrations.data.connector import get as get_connector

log = logging.getLogger("integrations.airtable_base")


class TableNotFoundError(Exception):
    """Error for table not found"""


def _idref(rec, field):
    v = rec["fields"].get(field)
    if v is None:
        return []
    if not isinstance(v, list):
        return [v]
    return v


def get_record(base, tbl, rec):
    """Grabs a record from a named table (from config.yaml)"""
    status, content = get_connector().db_request("GET", base, tbl, rec)
    if status != 200:
        raise RuntimeError(f"Airtable fetch {base} {tbl} {rec}", status, content)
    return content


def get_all_records(base, tbl, suffix=None):
    """Get all records for a given named table (ID in config.yaml)"""
    records = []
    offs = ""
    while offs is not None:
        s = f"?offset={offs}"
        if suffix is not None:
            s += "&" + suffix
        status, content = get_connector().db_request("GET", base, tbl, suffix=s)
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
            # Original implementation is with Airtable; NocoDB has a different response format
            # so we massage it to look like an Airtable response.
            records += [{"id": d["Id"], "fields": d} for d in data["list"]]
            if data["pageInfo"].get("isLastPage"):
                break
            offs = data["pageInfo"]["page"] * data["pageInfo"]["pageSize"]
        else:
            records += data["records"]
            if data.get("offset") is None:
                break
            offs = data["offset"]
    return records


def get_all_records_between(base, tbl, start_date, end_date, field="Created"):
    """Returns a list of all records in the table with the
    Created field timestamp after a certain date"""
    suffix = None
    if not end_date:
        return get_all_records_after(base, tbl, start_date, field)

    if get_connector().db_format() == "nocodb":
        suffix = f"where=({field},le,exactDate,{end_date.isoformat()})~and({field},ge,exactDate,{start_date.isoformat()})"  # pylint: disable=line-too-long
    else:
        suffix = f"filterByFormula=AND(IS_BEFORE(%7B{field}%7D, '{end_date.isoformat()}'), IS_AFTER(%7B{field}%7D,'{start_date.isoformat()}'))"  # pylint: disable=line-too-long

    return get_all_records(base, tbl, suffix=suffix)


def get_all_records_after(base, tbl, after_date, field="Created"):
    """Returns a list of all records in the table with the
    Created field timestamp after a certain date"""
    if get_connector().db_format() == "nocodb":
        suffix = f"where=({field},ge,exactDate,{after_date.isoformat()})"
    else:
        suffix = f"filterByFormula=IS_AFTER(%7B{field}%7D,'{after_date.isoformat()}')"

    return get_all_records(base, tbl, suffix=suffix)


def insert_records(records, base, tbl, link_fields=None):
    """Inserts one or more records into a named table. the "fields" structure is
    automatically applied.

    Note that link_records is only needed for NocoDB, as airtable auto-links in a
    single request.
    """
    # Max of 10 records allowed for insertion, see
    # https://airtable.com/developers/web/api/create-records
    assert len(records) <= 10

    post_data = {"records": [{"fields": d} for d in records]}
    status, content = get_connector().db_request("POST", base, tbl, data=post_data)

    if get_connector().db_format() != "nocodb" or link_fields is None:
        return status, content

    log.info(f"NocoDB: handling link fields {link_fields} for records {content}...")
    try:
        # NocoDB requires linking as a separate request (ugh).
        # https://github.com/nocodb/nocodb/issues/11138 tracks discussion on allowing
        # single-request inserts with link fields.
        for i, rec in enumerate(content):
            for lf in link_fields or []:
                val = records[i].get(lf)
                if val is None:
                    continue
                log.info(f"Linking {lf} in {rec['Id']} to {val}")
                if not isinstance(val, list):
                    val = [val]
                val = [{"Id": v} for v in val]
                lstatus, lcontent = get_connector().db_request(
                    "POST", base, tbl, rec["Id"], link_field=lf, data=val
                )
                log.info(f"Link result {lstatus}: {lcontent}")
                assert lstatus in (201, 200)
        return status, content
    except Exception as e:
        log.error("Rolling back / attempting to delete inserted records")
        status, content = get_connector().db_request("DELETE", base, tbl, content)
        assert status == 200
        raise RuntimeError(f"Failed to link record {rec['Id']}, field {lf}") from e


def update_record(data, base, tbl, rec):
    """Updates/patches a record in a named table"""
    post_data = {"fields": data}
    return get_connector().db_request("PATCH", base, tbl, rec=rec, data=post_data)


def delete_record(base, tbl, rec):
    """Deletes a record in a named table"""
    if get_connector().db_format() == "nocodb":
        return get_connector().db_request("DELETE", base, tbl, data=[{"Id": rec}])
    return get_connector().db_request("DELETE", base, tbl, rec=rec)


def link_record(
    base: str, tbl: str, rec: int, field: str, linked_record_ids: list[int]
):
    """NOCODB ONLY
    https://data-apis-v2.nocodb.com/#tag/Table-Records/operation/db-data-table-row-nested-list
    """
    return get_connector().db_request(
        "POST",
        base,
        tbl,
        rec,
        data=[{"Id": i} for i in linked_record_ids],
        link_field=field,
    )
