"""Tests for MQTT integration"""

from protohaven_api.integrations import mqtt as m


def test_on_connect(mocker):
    """Test MQTT on_connect function"""
    c = m.Client(None)
    mocker.patch.object(c, "c")
    c.on_connect(None, None, {}, 0, None)
    c.c.subscribe.assert_any_call(  # pylint: disable=no-member
        "/protohaven_api/v1/notify_discord"
    )
