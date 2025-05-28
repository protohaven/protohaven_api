"""Verify proper behavior of public access pages"""
# pylint: skip-file
import json

import pytest

from protohaven_api.app import configure_app
from protohaven_api.handlers import index
from protohaven_api.integrations import neon
from protohaven_api.rbac import set_rbac
from protohaven_api.testing import MatchStr, d, fixture_client, setup_session


def test_index(client):
    """Test behavior of index page"""
    setup_session(client)
    response = client.get("/")
    assert response.status_code == 302
    assert response.location == "/member"


def test_whoami(client):
    """test /whoami returns session info"""
    setup_session(client)
    response = client.get("/whoami")
    assert json.loads(response.data.decode("utf8")) == {
        "fullname": "First Last",
        "email": "foo@bar.com",
        "neon_id": 1234,
        "clearances": ["C1", "C2"],
        "roles": ["Board Member"],
    }


def test_class_listing(mocker, client):
    """Test class_listing function returns sorted class list with airtable data"""
    m1 = mocker.MagicMock(
        neon_id=1, start_date=d(0, 10), description="foo", airtable_data="bar"
    )
    m1.name = "m1"
    m2 = mocker.MagicMock(
        neon_id=2, start_date=d(0, 9), description="foo", airtable_data="baz"
    )
    m2.name = "m2"
    mocker.patch.object(index.eauto, "fetch_upcoming_events", return_value=[m1, m2])
    rep = client.get("/class_listing")
    assert json.loads(rep.data.decode("utf8")) == [
        {
            "id": 2,
            "name": "m2",
            "description": "foo",
            "timestamp": d(0, 9).isoformat(),
            "day": "Wednesday, Jan 1",
            "time": "9:00 AM",
            "airtable_data": "baz",
        },
        {
            "id": 1,
            "name": "m1",
            "description": "foo",
            "timestamp": d(0, 10).isoformat(),
            "day": "Wednesday, Jan 1",
            "time": "10:00 AM",
            "airtable_data": "bar",
        },
    ]
