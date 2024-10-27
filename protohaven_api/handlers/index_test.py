"""Verify proper behavior of public access pages"""
# pylint: skip-file
import json

import pytest

from protohaven_api.handlers import index
from protohaven_api.integrations import neon
from protohaven_api.main import app
from protohaven_api.rbac import set_rbac
from protohaven_api.testing import Any, MatchStr, d, fixture_client, setup_session


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
        "roles": ["test role"],
    }


def test_welcome_signin_get(client, mocker):
    """Check that the svelte page is loaded"""
    mocker.patch.object(app, "send_static_file", return_value="TEST")
    assert "TEST" == client.get("/welcome").data.decode("utf8")
    app.send_static_file.assert_called_with("svelte/welcome.html")


def test_class_listing(mocker):
    """Test class_listing function returns sorted class list with airtable data"""
    mocker.patch.object(
        index.neon,
        "fetch_published_upcoming_events",
        return_value=[
            {"id": 1, "startDate": "2025-01-01", "startTime": "10:00 AM"},
            {"id": 2, "startDate": "2025-01-01", "startTime": "9:00 AM"},
        ],
    )

    mocker.patch.object(
        index.airtable,
        "get_class_automation_schedule",
        return_value=[
            {"fields": {"Neon ID": "1", "Extra Info": "Info1"}},
            {"fields": {"Neon ID": "2", "Extra Info": "Info2"}},
        ],
    )

    expected_result = [
        {
            "id": 2,
            "startDate": "2025-01-01",
            "startTime": "9:00 AM",
            "timestamp": d(0, 9),
            "day": "Wednesday, Jan 1",
            "time": "9:00 AM",
            "airtable_data": {"fields": {"Neon ID": "2", "Extra Info": "Info2"}},
        },
        {
            "id": 1,
            "startDate": "2025-01-01",
            "startTime": "10:00 AM",
            "timestamp": d(0, 10),
            "day": "Wednesday, Jan 1",
            "time": "10:00 AM",
            "airtable_data": {"fields": {"Neon ID": "1", "Extra Info": "Info1"}},
        },
    ]

    got = index.class_listing()
    assert got == expected_result
