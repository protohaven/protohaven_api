"""A mock version of Eventbrite"""

import logging

from flask import Flask, Response, request

from protohaven_api.integrations import airtable_base

app = Flask(__file__)

log = logging.getLogger("integrations.data.dev_eventbrite")


@app.route("/organizations/<org_id>/events/", methods=["GET"])
def get_events(org_id):  # pylint: disable=unused-argument
    """Mock events endpoint for Neon - needs to be completed"""
    return {
        "events": [
            row["fields"]["data"]
            for row in airtable_base.get_all_records("fake_eventbrite", "events")
        ],
        "pagination": {"has_more_items": False},
    }


@app.route("/events/<evt_id>", methods=["GET"])
def get_event(evt_id):
    """Mock events endpoint for Neon - needs to be completed"""
    for row in airtable_base.get_all_records("fake_eventbrite", "events"):
        if str(row["fields"]["event_id"]) == str(evt_id):
            return row["fields"]["data"]

    return Response("Not found", status=404)


client = app.test_client()


@app.route("/organizations/<org_id>/discounts/", methods=["POST"])
def post_discount(_):
    """Stub discount creation handler"""
    code = request.json.get("discount").get("code")
    # Just pass the code right back
    return {"id": code}


def handle(mode, url, params=None):  # pylint: disable=unused-argument
    """Local execution of mock flask endpoints for Eventbrite"""
    if mode == "GET":
        return client.get(url)
    if mode == "POST":
        return client.post(url)
    raise RuntimeError(f"mode not supported: {mode}")
