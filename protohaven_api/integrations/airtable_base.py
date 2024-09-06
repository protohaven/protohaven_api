"""Airtable basic API commands"""
import json

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector


def cfg(base):
    """Get config for airtable stuff"""
    return get_config()["airtable"][base]


def get_record(base, tbl, rec):
    """Grabs a record from a named table (from config.yaml)"""
    status, content = get_connector().airtable_request("GET", base, tbl, rec)
    if status != 200:
        raise RuntimeError(f"Airtable fetch {base} {tbl} {rec}", status, content)
    return json.loads(content)


def get_all_records(base, tbl, suffix=None):
    """Get all records for a given named table (ID in config.yaml)"""
    records = []
    offs = ""
    while offs is not None:
        s = f"?offset={offs}"
        if suffix is not None:
            s += "&" + suffix
        status, content = get_connector().airtable_request("GET", base, tbl, suffix=s)
        if status != 200:
            raise RuntimeError(
                f"Airtable fetch {base} {tbl} {s}",
                status,
                content,
            )
        data = json.loads(content)
        records += data["records"]
        if data.get("offset") is None:
            break
        offs = data["offset"]
    return records


def get_all_records_after(base, tbl, after_date):
    """Returns a list of all records in the table with the
    Created field timestamp after a certain date"""
    return get_all_records(
        base,
        tbl,
        suffix=f"filterByFormula=IS_AFTER(%7BCreated%7D,'{after_date.isoformat()}')",
    )


def insert_records(data, base, tbl):
    """Inserts one or more records into a named table. the "fields" structure is
    automatically applied."""
    # Max of 10 records allowed for insertion, see
    # https://airtable.com/developers/web/api/create-records
    assert len(data) <= 10
    post_data = {"records": [{"fields": d} for d in data]}
    status, content = get_connector().airtable_request(
        "POST", base, tbl, data=json.dumps(post_data)
    )
    return status, json.loads(content) if content else None


def update_record(data, base, tbl, rec):
    """Updates/patches a record in a named table"""
    post_data = {"fields": data}
    status, content = get_connector().airtable_request(
        "PATCH", base, tbl, rec=rec, data=json.dumps(post_data)
    )
    return status, json.loads(content) if content else None


def delete_record(base, tbl, rec):
    """Deletes a record in a named table"""
    status, content = get_connector().airtable_request("DELETE", base, tbl, rec=rec)
    return status, json.loads(content) if content else None
