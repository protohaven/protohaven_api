"""Test methods for comms-oriented CLI commands"""
# pylint: skip-file
import pytest

from protohaven_api.commands import comms as c


@pytest.fixture
def mock_e(mocker):
    mocker.patch.object(c.comms, "send_discord_message")
    mocker.patch.object(c.comms, "send_email")
    mocker.patch.object(c.airtable, "log_intents_notified")
    mocker.patch.object(c.airtable, "log_comms")
    mocker.patch.object(c.neon, "set_event_scheduled_state")
    return c, c.Commands()


def test_send_comms_email_no_id(mock_e, mocker):
    """Tes comms sent without an id (most basic)"""
    e, cmd = mock_e
    mocker.patch.object(
        cmd,
        "load_comms_data",
        return_value=[
            {
                "target": "a@a.com",
                "subject": "Test Subject",
                "body": "Test Body",
            },
        ],
    )
    cmd.send_comms(["--path", "/asdf/ghsdf", "--confirm"])
    e.comms.send_email.assert_called_with("Test Subject", "Test Body", ["a@a.com"])
    e.airtable.log_comms.assert_called_with("", "a@a.com", "Test Subject", "Sent")
    e.comms.send_discord_message.assert_not_called()
    e.airtable.log_intents_notified.assert_not_called()
    e.neon.set_event_scheduled_state.assert_not_called()


def test_send_comms_email_with_id(mock_e, mocker):
    """Test comms sent with an ID"""
    e, cmd = mock_e
    mocker.patch.object(
        cmd,
        "load_comms_data",
        return_value=[
            {
                "target": "a@a.com",
                "subject": "Test Subject",
                "body": "Test Body",
                "id": "123",
            },
        ],
    )
    cmd.send_comms(["--path", "/asdf/ghsdf", "--confirm"])
    e.comms.send_email.assert_called_with("Test Subject", "Test Body", ["a@a.com"])
    e.airtable.log_comms.assert_called_with("123", "a@a.com", "Test Subject", "Sent")
    e.comms.send_discord_message.assert_not_called()
    e.airtable.log_intents_notified.assert_not_called()
    e.neon.set_event_scheduled_state.assert_not_called()


def test_send_comms_discord_dm(mock_e, mocker):
    """Test comms sent via DM"""
    e, cmd = mock_e
    mocker.patch.object(
        cmd,
        "load_comms_data",
        return_value=[
            {
                "target": "@discorduser",
                "subject": "Test Subject",
                "body": "Test Body",
                "id": "123",
            },
        ],
    )
    cmd.send_comms(["--path", "/asdf/ghsdf", "--confirm"])
    e.comms.send_email.assert_not_called()
    e.airtable.log_comms.assert_called_with(
        "123", "@discorduser", "Test Subject", "Sent"
    )
    e.comms.send_discord_message.assert_called_with(
        "Test Subject\n\nTest Body", "@discorduser"
    )
    e.airtable.log_intents_notified.assert_not_called()
    e.neon.set_event_scheduled_state.assert_not_called()


def test_send_comms_discord_channel(mock_e, mocker):
    """Test comms sent to a discord channel"""
    e, cmd = mock_e
    mocker.patch.object(
        cmd,
        "load_comms_data",
        return_value=[
            {
                "target": "#channel",
                "subject": "Test Subject",
                "body": "Test Body",
                "id": "123",
            },
        ],
    )
    cmd.send_comms(["--path", "/asdf/ghsdf", "--confirm"])
    e.comms.send_email.assert_not_called()
    e.airtable.log_comms.assert_called_with("123", "#channel", "Test Subject", "Sent")
    e.comms.send_discord_message.assert_called_with(
        "Test Subject\n\nTest Body", "#channel"
    )
    e.airtable.log_intents_notified.assert_not_called()
    e.neon.set_event_scheduled_state.assert_not_called()


def test_send_comms_side_effect_cancellation(mock_e, mocker):
    """Test comms with class cancellation side effect"""
    e, cmd = mock_e
    mocker.patch.object(
        cmd,
        "load_comms_data",
        return_value=[
            {
                "target": "@testuser",
                "subject": "Test Subject",
                "body": "Test Body",
                "side_effect": {"cancel": 12345},
            },
        ],
    )
    cmd.send_comms(["--path", "/asdf/ghsdf", "--confirm"])
    e.neon.set_event_scheduled_state.assert_called_with("12345", scheduled=False)


def test_send_comms_intent(mock_e, mocker):
    """Test comms with an `intent` setting (for Discord automation table updating)"""
    e, cmd = mock_e
    mocker.patch.object(
        cmd,
        "load_comms_data",
        return_value=[
            {
                "target": "#channel",
                "subject": "Test Subject",
                "body": "Test Body",
                "intents": ["a", "b"],
            },
        ],
    )
    cmd.send_comms(["--path", "/asdf/ghsdf", "--confirm"])
    e.airtable.log_intents_notified.assert_called_with(["a", "b"])


def test_send_comms_dryrun_does_nothing(mock_e, mocker):
    """Test that the dry_run flag does not trigger airtable mutations or sending"""
    e, cmd = mock_e
    mocker.patch.object(
        cmd,
        "load_comms_data",
        return_value=[
            {
                "target": "#channel",
                "subject": "Test Subject",
                "body": "Test Body",
                "intents": ["a", "b"],
                "id": "123",
            },
            {
                "target": "a@b.com",
                "subject": "Test Subject",
                "body": "Test Body",
                "intents": ["a", "b"],
                "id": "123",
                "side_effect": {"cancel": 12345},
            },
        ],
    )
    cmd.send_comms(["--path", "/asdf/ghsdf", "--confirm", "--dryrun"])
    e.airtable.log_intents_notified.assert_not_called()
    e.airtable.log_comms.assert_not_called()
    e.neon.set_event_scheduled_state.assert_not_called()
    e.comms.send_discord_message.assert_not_called()
    e.comms.send_email.assert_not_called()
