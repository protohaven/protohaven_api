"""Testing comms integration methods"""

from protohaven_api.integrations import comms as c


def test_send_discord_message_with_role_embed(mocker):
    """Ensure that @role mentions are properly converted to role IDs"""
    mocker.patch.object(
        c,
        "get_config",
        return_value={
            "comms": {
                "test_channel": "https://test_channel_webhook",
                "discord_roles": {"TestRole": "TEST_ROLE_ID"},
            }
        },
    )
    mocker.patch.object(c, "get_connector")
    c.send_discord_message("Hello @TestRole!", "#test_channel")
    c.get_connector().discord_webhook.assert_called_with(  # pylint: disable=no-member
        "https://test_channel_webhook", "Hello <@&TEST_ROLE_ID>!"
    )


def test_send_discord_message_dm(mocker):
    """Ensure #user targets are sent via DM"""
    mocker.patch.object(
        c,
        "get_config",
        return_value={
            "comms": {
                "test_channel": "https://test_channel_webhook",
                "discord_roles": {"TestRole": "TEST_ROLE_ID"},
            }
        },
    )
    mocker.patch.object(c, "get_connector")
    c.send_discord_message("Test content", "@testuser")
    c.get_connector().discord_bot_send_dm.assert_called_with(  # pylint: disable=no-member
        "testuser", "Test content"
    )
