"""A mock version of Booked serving results pulled from mock_data"""

from urllib.parse import urlparse

from flask import Flask

app = Flask(__file__)


@app.route("/Reservations/")
def get_events():
    """Mock events endpoint for Neon - needs to be completed"""
    # start = dateparser.parse(request.values["startDateTime"])
    # end = dateparser.parse(request.values["endDateTime"])
    # for m in mock_data["booked"]...
    return {"reservations": []}


client = app.test_client()


def handle(mode, url, json=None):
    """Local execution of mock flask endpoints for Booked"""
    url = urlparse(url).path
    if mode == "GET":
        return client.get(url)
    if mode == "POST":
        return client.post(url, json=json)
    raise RuntimeError(f"mode not supported: {mode}")
