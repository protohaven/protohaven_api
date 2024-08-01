import json
import uuid
from dataclasses import dataclass
from functools import cache
from urllib.parse import urlparse

from flask import Flask, Response, request

from protohaven_api.config import get_config
from protohaven_api.integrations.data.loader import mock_data

app = Flask(__file__)


@cache
def _base_lookup(id):
    cfg = get_config()["airtable"]
    return {v["base_id"]: k for k, v in cfg.items()}[id]


@cache
def _tbl_lookup(id):
    cfg = get_config()["airtable"]
    return {v: k for tbl in cfg.values() for k, v in tbl.items()}[id]


@app.route("/v0/<base>/<tbl>", methods=["GET", "POST"])
def recordless_op(base, tbl):
    tbl = mock_data["airtable"][_base_lookup(base)][_tbl_lookup(tbl)]
    if request.method == "GET":
        return {"records": tbl}
    elif request.method == "POST":
        for rec in request.json["records"]:
            rec["id"] = str(uuid.uuid4().hex)
            tbl.append(rec)
    else:
        return Response("Method not supported", status=400)


@app.route("/v0/<base>/<tbl>/<rec>", methods=["GET", "PATCH"])
def single_record_op(base, tbl, rec):
    for r in mock_data["airtable"][_base_lookup(base)][_tbl_lookup(tbl)]:
        if r["id"] == rec:
            break
    if r["id"] != rec:
        return Response("Record Not Found", status=404)
    if request.method == "GET":
        return r
    elif request.method == "PATCH":
        for k, v in request.json["fields"].items():
            r["fields"][k] = v
        return r
    else:
        return Response("Method not supported", status=400)


client = app.test_client()


def handle(mode, url, data):
    """Dev handler for airtable web requests"""
    url = urlparse(url).path
    if mode == "GET":
        return client.get(url)
    elif mode == "POST":
        return client.post(url, json=json.loads(data))
    elif mode == "PATCH":
        return client.patch(url, json=json.loads(data))
