"""A mock version of Booked"""

import logging

from flask import Flask, request

from protohaven_api.config import safe_parse_datetime
from protohaven_api.integrations import airtable_base

app = Flask(__file__)

log = logging.getLogger("integrations.data.dev_booked")


@app.route("/Reservations/", methods=["GET", "POST"])
def get_reservations():
    """Mock events endpoint for Neon - needs to be completed"""
    if request.method == "POST":
        raise NotImplementedError(
            f"Unhandled dev POST to /Reservations/: {request.data}"
        )

    start = safe_parse_datetime(request.values.get("startDateTime"))
    end = safe_parse_datetime(request.values.get("endDateTime"))
    return {
        "reservations": [
            row["fields"]["data"]
            for row in airtable_base.get_all_records("fake_booked", "reservations")
            if start <= safe_parse_datetime(row["fields"]["start"]) <= end
        ],
        "startDateTime": start,
        "endDateTime": end,
        "links": [],
        "message": None,
    }


client = app.test_client()


def handle(mode, url, json=None):
    """Local execution of mock flask endpoints for Booked"""
    if mode == "GET":
        return client.get(url)
    if mode == "POST":
        return client.post(url, json=json)
    raise RuntimeError(f"mode not supported: {mode}")
