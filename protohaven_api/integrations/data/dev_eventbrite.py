"""A mock version of Eventbrite"""

import logging
import uuid

from flask import Flask, Response, request

from protohaven_api.integrations import airtable_base

app = Flask(__file__)

log = logging.getLogger("integrations.data.dev_eventbrite")


@app.route("/organizations/<org_id>/events/", methods=["GET"])
def get_events(org_id):  # pylint: disable=unused-argument
    """Mock Eventbrite organization event list"""
    return {
        "events": [
            row["fields"]["data"]
            for row in airtable_base.get_all_records("fake_eventbrite", "events")
        ],
        "pagination": {"has_more_items": False},
    }


@app.route("/organizations/<org_id>/events/", methods=["POST"])
def post_event(org_id):  # pylint: disable=unused-argument
    """Mock Eventbrite event creation"""
    event_data = request.json.get("event", {})
    event_id = str(uuid.uuid4())
    airtable_base.insert_records(
        [{"event_id": event_id, "data": {"id": event_id, **event_data}}],
        "fake_eventbrite",
        "events",
    )
    return {"id": event_id}


@app.route("/events/<evt_id>", methods=["GET", "DELETE"])
def event(evt_id):
    """Mock single event fetch and deletion"""
    if request.method == "DELETE":
        return {"deleted": True}
    for row in airtable_base.get_all_records("fake_eventbrite", "events"):
        if str(row["fields"]["event_id"]) == str(evt_id):
            return row["fields"]["data"]

    return Response("Not found", status=404)


client = app.test_client()


@app.route("/organizations/<org_id>/discounts/", methods=["POST"])
def post_discount(org_id):  # pylint: disable=unused-argument
    """Stub discount creation handler"""
    code = request.json.get("discount").get("code")
    # Just pass the code right back
    return {"code": code}


@app.route("/orders/", methods=["POST"])
def post_order():
    """Stub Eventbrite order creation"""
    order = request.json.get("order", {})
    return {"id": "1", **order}


@app.route("/orders/<order_id>/cancel/", methods=["POST"])
def post_cancel_order(order_id):
    """Stub Eventbrite free order cancellation"""
    return {"id": order_id, "cancelled": True}


@app.route("/events/<evt_id>/ticket_classes/", methods=["POST"])
def post_ticket_class(evt_id):  # pylint: disable=unused-argument
    """Stub Eventbrite ticket class creation"""
    return {"resource_uri": f"/ticket_class/{uuid.uuid4()}/"}


@app.route("/events/<evt_id>/ticket_classes/<ticket_class_id>/", methods=["DELETE"])
def delete_ticket_class(evt_id, ticket_class_id):  # pylint: disable=unused-argument
    """Stub Eventbrite ticket class deletion"""
    return {"deleted": True}


@app.route("/events/<evt_id>/publish/", methods=["POST"])
def publish_event(evt_id):  # pylint: disable=unused-argument
    """Stub Eventbrite event publishing"""
    return {"published": True}


@app.route("/events/<evt_id>/unpublish/", methods=["POST"])
def unpublish_event(evt_id):  # pylint: disable=unused-argument
    """Stub Eventbrite event unpublishing"""
    return {"unpublished": True}


@app.route("/events/<evt_id>/structured_content/<content_version>/", methods=["POST"])
def post_structured_content(evt_id, content_version):  # pylint: disable=unused-argument
    """Stub Eventbrite structured content update"""
    return {"page_version_number": int(content_version)}


@app.route("/events/<evt_id>/attendees/", methods=["GET"])
def get_attendees(evt_id):  # pylint: disable=unused-argument
    """Stub Eventbrite attendee list"""
    return {"attendees": [], "pagination": {"has_more_items": False}}


@app.route("/media/upload/", methods=["GET", "POST"])
def media_upload():
    """Stub Eventbrite media upload token and confirm endpoints"""
    if request.method == "GET":
        return {
            "upload_url": "https://s3.example/upload",
            "upload_data": {"key": "value"},
            "file_parameter_name": "file",
            "upload_token": str(uuid.uuid4()),
        }
    return {"id": request.json.get("upload_token", "logo_1")}


def handle(mode, url, params=None, json=None):  # pylint: disable=unused-argument
    """Local execution of mock flask endpoints for Eventbrite"""
    if mode == "GET":
        return client.get(url)
    if mode == "POST":
        return client.post(url, json=json)
    if mode == "DELETE":
        return client.delete(url)
    raise RuntimeError(f"mode not supported: {mode}")
