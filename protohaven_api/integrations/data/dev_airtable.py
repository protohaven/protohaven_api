"""Mock airtable service using canned data"""
import json
import uuid
from functools import cache
from urllib.parse import urlparse

from flask import Flask, Response, request

from protohaven_api.config import get_config
from protohaven_api.integrations.data.loader import mock_data

app = Flask(__file__)


@cache
def _base_lookup(_id):
    """Lookup base within config.yaml"""
    cfg = get_config()["airtable"]
    return {v["base_id"]: k for k, v in cfg.items()}[_id]


@cache
def _tbl_lookup(_id):
    """Lookup table within config.yaml"""
    cfg = get_config()["airtable"]
    return {v: k for tbl in cfg.values() for k, v in tbl.items()}[_id]


@app.route("/v0/<base>/<tbl>", methods=["GET", "POST"])
def recordless_op(base, tbl):
    """Perform CRUD operations on canned data, without referencing a record"""
    tbl = mock_data()["airtable"][_base_lookup(base)][_tbl_lookup(tbl)]
    if request.method == "GET":
        return {"records": tbl}
    if request.method == "POST":
        rep = []
        for rec in request.json["records"]:
            rec["id"] = str(uuid.uuid4().hex)
            tbl.append(rec)
            rep.append(rec)
        return {"records": rep}
    return Response("Method not supported", status=400)


@app.route("/v0/<base>/<tbl>/<rec>", methods=["GET", "PATCH"])
def single_record_op(base, tbl, rec):
    """Perform CRUD operations on canned data for a single record"""
    r = {}
    for r in mock_data()["airtable"][_base_lookup(base)][_tbl_lookup(tbl)]:
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
    return RuntimeError(f"Req not supported with mode {mode}")
