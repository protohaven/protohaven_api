"""Airtable basic API commands"""

from protohaven_api.integrations.data.connector import get as get_connector


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


def insert_records(data, base, tbl):
    """Inserts one or more records into a named table. the "fields" structure is
    automatically applied."""
    # Max of 10 records allowed for insertion, see
    # https://airtable.com/developers/web/api/create-records
    assert len(data) <= 10
    post_data = {"records": [{"fields": d} for d in data]}
    return get_connector().db_request("POST", base, tbl, data=post_data)


def update_record(data, base, tbl, rec):
    """Updates/patches a record in a named table"""
    post_data = {"fields": data}
    return get_connector().db_request("PATCH", base, tbl, rec=rec, data=post_data)


def delete_record(base, tbl, rec):
    """Deletes a record in a named table"""
    return get_connector().db_request("DELETE", base, tbl, rec=rec)
