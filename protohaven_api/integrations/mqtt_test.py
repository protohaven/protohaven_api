"""Tests for MQTT integration"""

from protohaven_api.integrations import mqtt as m


def test_on_connect(mocker):
    """Test MQTT on_connect function"""
    c = m.Client()
    mocker.patch.object(c, "c")
    c.on_connect(None, None, {}, 0, None)
    for topic in m.TOPICS:
        for prefix in m.SUB_PREFIXES:
            c.c.subscribe.assert_any_call(  # pylint: disable=no-member
                f"{prefix}/+/{topic}"
            )


def test_on_shopminder_alive_msg(mocker):
    """Test MQTT on_message function"""
    c = m.Client()
    mocker.patch.object(c, "c")
    c.on_message(None, None, mocker.MagicMock(topic="prefix/minder/ALIVE", payload="1"))
    assert c.shopminders["minder"]["alive"]

    c.on_message(None, None, mocker.MagicMock(topic="prefix/minder/ALIVE", payload="0"))
    assert not c.shopminders["minder"]["alive"]
