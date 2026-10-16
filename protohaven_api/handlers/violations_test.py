"""Verify proper behavior of policy violation handlers"""

# pylint: skip-file
import io

import pytest

from protohaven_api.handlers import violations as vl
from protohaven_api.integrations.models import Role
from protohaven_api.testing import d, fixture_client, setup_session


@pytest.fixture()
def tech_client(client):
    setup_session(client, [Role.SHOP_TECH])
    return client


def test_violation_sections(tech_client, mocker):
    """The violations page can fetch policy sections"""
    mocker.patch.object(
        vl.airtable,
        "get_policy_sections",
        return_value=[
            {"id": "sec1", "fields": {"Section": "Storage"}},
            {"id": "sec2", "fields": {"Section": "Equipment damage"}},
        ],
    )
    response = tech_client.get("/violations/sections")
    assert response.status_code == 200
    assert response.json == [
        {"id": "sec1", "name": "Storage"},
        {"id": "sec2", "name": "Equipment damage"},
    ]


def test_violations(tech_client, mocker):
    """The violations list resolves member names without exposing Neon IDs"""
    mocker.patch.object(
        vl.airtable,
        "get_policy_sections",
        return_value=[{"id": "sec1", "fields": {"Section": "Storage"}}],
    )
    mocker.patch.object(
        vl.airtable,
        "get_policy_fees",
        return_value=[
            {
                "fields": {
                    "Violation": ["v1"],
                    "Amount": 5,
                    "Paid": False,
                }
            }
        ],
    )
    mocker.patch.object(
        vl.airtable,
        "get_policy_violations",
        return_value=[
            {
                "id": "v1",
                "fields": {
                    "Instance #": 1,
                    "Neon ID": 123,
                    "Onset": d(0).isoformat(),
                    "Relevant Sections": ["sec1"],
                    "Notes": "note",
                    "Daily Fee": 5,
                    "Accrued": 10,
                },
            }
        ],
    )
    mocker.patch.object(
        vl.neon_base,
        "fetch_account",
        return_value=mocker.MagicMock(fname="Test", lname="User", email="a@b.com"),
    )
    response = tech_client.get("/violations")
    assert response.status_code == 200
    violation = response.json[0]
    assert violation["suspect_name"] == "Test User"
    assert violation["suspect_email"] == "a@b.com"
    assert violation["sections"] == ["Storage"]
    assert violation["unpaid_fees"] == 5
    assert "neon_id" not in violation


def test_open_violation(tech_client, mocker):
    """The new violation endpoint passes sanitized data to Airtable"""
    open_violation = mocker.patch.object(
        vl.airtable, "open_violation", return_value="v1"
    )
    response = tech_client.post(
        "/violations/open",
        json={
            "reporter": "Shop Tech",
            "neon_id": None,
            "tag_number": "4",
            "onset": d(0).isoformat(),
            "sections": ["sec1"],
            "notes": "Left a cart out",
            "evidence": "https://example.com/a.jpg\nhttps://example.com/b.jpg",
            "daily_fee": "15",
        },
    )
    assert response.status_code == 200
    assert response.json == {"ok": True, "id": "v1"}
    assert open_violation.call_args.kwargs["reporter"] == "Shop Tech"
    assert open_violation.call_args.kwargs["tag_number"] == "4"
    assert open_violation.call_args.kwargs["fee"] == 15.0
    assert open_violation.call_args.kwargs["evidence"] == [
        "https://example.com/a.jpg",
        "https://example.com/b.jpg",
    ]


def test_upload_violation_evidence(tech_client, mocker):
    """The evidence endpoint uploads pictures to the violation record"""
    upload = mocker.patch.object(vl.airtable, "upload_violation_evidence")
    response = tech_client.post(
        "/violations/v1/evidence",
        data={
            "files": [
                (io.BytesIO(b"abc"), "a.jpg", "image/jpeg"),
                (io.BytesIO(b"defg"), "b.jpg", "image/jpeg"),
            ]
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert response.json == {"ok": True}
    uploaded = upload.call_args.args[1]
    assert [u[0] for u in uploaded] == ["a.jpg", "b.jpg"]
    assert [u[1] for u in uploaded] == ["image/jpeg", "image/jpeg"]
    assert [u[2] for u in uploaded] == [b"abc", b"defg"]


def test_close_violation(tech_client, mocker):
    """The close endpoint creates a closure record"""
    close_violation = mocker.patch.object(vl.airtable, "close_violation")
    response = tech_client.post(
        "/violations/v1/close",
        json={
            "closer": "Shop Tech <tech@protohaven.org>",
            "close_date": d(0).isoformat(),
            "notes": "Fees paid",
            "fees_outstanding": True,
        },
    )
    assert response.status_code == 200
    assert close_violation.call_args.args[0] == "v1"
    assert (
        close_violation.call_args.kwargs["closer"] == "Shop Tech <tech@protohaven.org>"
    )
    assert close_violation.call_args.kwargs["fees_outstanding"] is True
