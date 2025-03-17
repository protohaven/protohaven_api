"""Mock airtable service using canned data"""

import json
import logging
import uuid
from functools import lru_cache
from urllib.parse import urlparse

from flask import Flask, Response, request

from protohaven_api.config import get_config, mock_data

app = Flask(__file__)


log = logging.getLogger("integrations.data.dev_airtable")


@lru_cache(maxsize=128)
def _base_lookup(_id):
    """Lookup base within config.yaml"""
    return {v["base_id"]: k for k, v in get_config("airtable").items()}[_id]


@lru_cache(maxsize=128)
def _tbl_lookup(_id):
    """Lookup table within config.yaml"""
    return {v: k for tbl in get_config("airtable").values() for k, v in tbl.items()}[
        _id
    ]


@app.route("/v0/<base>/<tbl>", methods=["GET", "POST"])
def recordless_op(base, tbl):
    """Perform CRUD operations on canned data, without referencing a record"""
    t = mock_data()["airtable"][_base_lookup(base)][_tbl_lookup(tbl)]
    if request.method == "GET":
        return {"records": t}
    if request.method == "POST":
        rep = []
        for rec in request.json["records"]:
            rec["id"] = str(uuid.uuid4().hex)
            t.append(rec)
            rep.append(rec)
        log.info(f"Airtable add records: {rep}")
        check = mock_data()["airtable"][_base_lookup(base)][_tbl_lookup(tbl)]
        log.info(f"Value in table: {check[-1]}")
        return {"records": rep}
    return Response("Method not supported", status=400)


@app.route("/v0/<base>/<tbl>/<rec>", methods=["GET", "PATCH", "DELETE"])
def single_record_op(base, tbl, rec):
    """Perform CRUD operations on canned data for a single record"""
    r = {}
    t = mock_data()["airtable"][_base_lookup(base)][_tbl_lookup(tbl)]
    for r in t:
        if r["id"] == rec:
            break
    if r["id"] != rec:
        return Response("Record Not Found", status=404)
    if request.method == "GET":
        return r
    if request.method == "PATCH":
        for k, v in request.json["fields"].items():
            r["fields"][k] = v
        return r
    if request.method == "DELETE":
        rep = {"id": r["id"], "deleted": True}
        t.remove(r)
        return rep
    return Response("Method not supported", status=400)


client = app.test_client()


def handle(mode, url, data):
    """Dev handler for airtable web requests"""
    url = urlparse(url).path
    if mode == "GET":
        return client.get(url)
    if mode == "POST":
        return client.post(url, json=json.loads(data))
    if mode == "PATCH":
        return client.patch(url, json=json.loads(data))
    if mode == "DELETE":
        return client.delete(url, json=data)
    raise RuntimeError(f"Req not supported with mode {mode}")
