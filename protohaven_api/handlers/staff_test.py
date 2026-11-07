# pylint: skip-file
"""Verify staff page access controls"""

import json

from protohaven_api.handlers import staff
from protohaven_api.integrations.models import Role
from protohaven_api.testing import fixture_client, setup_session


def test_staff_page_denied_to_non_staff(client):
    """A logged-in non-staff account cannot load the staff dashboard."""
    setup_session(client, [Role.SHOP_TECH])

    response = client.get("/staff")

    assert response.status_code == 401
    assert b"Access Denied" in response.data


def test_staff_discord_channels_denied_to_hello_testmember(client):
    """The exact non-staff member in the QA checklist cannot access staff APIs."""
    setup_session(client, [Role.SHOP_TECH])
    with client.session_transaction() as session:
        session["neon_account"]["individualAccount"]["primaryContact"][
            "email1"
        ] = "hello+testmember@protohaven.org"

    response = client.get("/staff/discord_member_channels")

    assert response.status_code == 401
    assert b"Access Denied" in response.data


def test_discord_channels_lists_member_channel_names(client, mocker):
    """discord_channels returns only the channel names."""
    setup_session(client, [Role.STAFF])
    mocker.patch.object(
        staff.comms,
        "get_member_channels",
        return_value=[("id1", "#general"), ("id2", "#random")],
    )

    response = client.get("/staff/discord_member_channels")

    assert response.status_code == 200
    assert response.json == ["#general", "#random"]


def test_summarizer_ws_streams_messages_and_summaries(mocker):
    """summarizer_ws reads a request, streams channel data, and sends summaries."""
    from protohaven_api.config import safe_parse_datetime
    from protohaven_api.handlers import staff

    ws = mocker.MagicMock()
    ws.receive.return_value = (
        '{"start_date": "2025-01-01T00:00:00-05:00", '
        '"end_date": "2025-01-02T00:00:00-05:00", '
        '"channels": ["#general"]}'
    )
    mocker.patch.object(
        staff.comms,
        "get_member_channels",
        return_value=[("id1", "#general"), ("id2", "#random")],
    )
    mocker.patch.object(
        staff.comms,
        "get_channel_history",
        return_value=[
            {
                "ref": "https://discord.example/1",
                "created_at": safe_parse_datetime("2025-01-01T10:00:00-05:00"),
                "images": ["https://example.com/a.jpg"],
                "videos": [],
                "content": "hello",
                "author": "Ada",
            }
        ],
    )
    mocker.patch.object(staff.gpt, "summary_summarizer", return_value="Final summary")

    staff.summarizer_ws(ws)

    sends = [call.args[0] for call in ws.send.call_args_list]
    assert any('"individual"' in s and "hello" in s for s in sends)
    assert any('"channel_summary"' in s and "Too few messages" in s for s in sends)
    assert any('"final_summary"' in s and "<p>Final summary</p>" in s for s in sends)
    ws.close.assert_called_once()


def test_ops_summary_ws_streams_ops_items(mocker):
    """ops_summary_ws serializes and sends each OpsItem produced by the report."""
    from protohaven_api.automation.reporting.ops_report import OpsItem
    from protohaven_api.handlers import staff

    ws = mocker.MagicMock()

    def run():
        yield OpsItem(category="Facilities", label="Front door locked", value="Locked")
        yield OpsItem(category="Facilities", label="Back door locked", value="Locked")

    mocker.patch.object(staff.ops_report, "run", side_effect=run)

    staff.ops_summary_ws(ws)

    assert ws.send.call_count == 2
    payloads = [json.loads(call.args[0]) for call in ws.send.call_args_list]
    assert payloads[0]["category"] == "Facilities"
    assert payloads[0]["label"] == "Front door locked"
    assert payloads[0]["value"] == "Locked"
    ws.close.assert_called_once()
