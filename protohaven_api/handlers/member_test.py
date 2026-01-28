"""Tests for member handlers"""

from protohaven_api.integrations import eventbrite, neon
from protohaven_api.testing import fixture_client  # pylint: disable=unused-import


def test_goto_class_eventbrite_member_not_found(client, mocker):
    """Test redirect when member not found in Neon"""
    with client.session_transaction() as sess:
        sess["neon_id"] = "123"
    mocker.patch.object(eventbrite, "is_valid_id", return_value=True)
    mocker.patch.object(neon, "search_member_by_neon_id", return_value=None)
    response = client.get("/member/goto_class?id=123")
    assert response.status_code == 400
    assert response.data == b"Error fetching membership for #123 - not found"


def test_goto_class_eventbrite_no_discount(mocker, client):
    """Test redirect to Eventbrite with no discount"""
    evt = "838895217177"
    with client.session_transaction() as sess:
        sess["neon_id"] = "123"
    mock_member = mocker.Mock(event_discount_pct=lambda: 0)
    mocker.patch.object(neon, "search_member_by_neon_id", return_value=mock_member)
    mocker.patch.object(eventbrite, "is_valid_id", return_value=True)
    response = client.get("/member/goto_class?id=" + evt)
    assert response.status_code == 302
    assert response.headers["Location"] == f"https://www.eventbrite.com/e/{evt}/"


def test_goto_class_eventbrite_with_discount(mocker, client):
    """Test redirect to Eventbrite with discount code"""
    evt = "838895217177"
    with client.session_transaction() as sess:
        sess["neon_id"] = "123"
    mock_member = mocker.Mock(event_discount_pct=lambda: 25)
    mocker.patch.object(neon, "search_member_by_neon_id", return_value=mock_member)
    mocker.patch.object(eventbrite, "is_valid_id", return_value=True)
    mocker.patch.object(eventbrite, "generate_discount_code", return_value="ABC")
    response = client.get("/member/goto_class?id=" + evt)
    eventbrite.generate_discount_code.assert_called_with(  # pylint: disable=no-member
        evt, 25
    )
    assert response.status_code == 302
    assert (
        response.headers["Location"]
        == f"https://www.eventbrite.com/e/{evt}/?discount=ABC"
    )


def test_goto_class_neon_event(mocker, client):
    """Test redirect to Neon event"""
    evt = "1234"
    with client.session_transaction() as sess:
        sess["neon_id"] = "123"
    mocker.patch.object(eventbrite, "is_valid_id", return_value=False)
    response = client.get("/member/goto_class?id=" + evt)
    assert response.status_code == 302
    assert (
        response.headers["Location"]
        == "https://protohaven.app.neoncrm.com/np/clients/protohaven/event.jsp?event="
        + evt
    )
