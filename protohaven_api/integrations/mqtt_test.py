"""Tests for MQTT integration"""

import json

from protohaven_api.integrations import mqtt as m


def test_on_connect(mocker):
    """Test MQTT on_connect function subscribes to default topics"""
    c = m.Client(None)
    mocker.patch.object(c, "c")
    c.on_connect(None, None, {}, 0, None)
    c.c.subscribe.assert_any_call(  # pylint: disable=no-member
        "/protohaven_api/v1/notify_discord"
    )


def test_register_topic_callback(mocker):
    """Test registering a topic callback"""
    c = m.Client(None)
    mocker.patch.object(c, "c")
    cb = lambda topic, data: None

    # Register when not connected - should not subscribe yet
    c.c.is_connected.return_value = False
    c.register_topic_callback("test/topic", cb)
    assert "test/topic" in c._topic_callbacks
    assert cb in c._topic_callbacks["test/topic"]
    c.c.subscribe.assert_not_called()


def test_register_topic_callback_connected(mocker):
    """Test registering a topic callback when already connected"""
    c = m.Client(None)
    mocker.patch.object(c, "c")
    cb = lambda topic, data: None

    c.c.is_connected.return_value = True
    c.register_topic_callback("test/topic", cb)
    c.c.subscribe.assert_called_once_with("test/topic")


def test_unregister_topic_callback(mocker):
    """Test unregistering a topic callback"""
    c = m.Client(None)
    mocker.patch.object(c, "c")
    cb1 = lambda topic, data: None
    cb2 = lambda topic, data: None

    c.c.is_connected.return_value = True
    c.register_topic_callback("test/topic", cb1)
    c.register_topic_callback("test/topic", cb2)

    # Unregister one callback - should keep topic subscribed
    c.unregister_topic_callback("test/topic", cb1)
    assert cb1 not in c._topic_callbacks["test/topic"]
    assert cb2 in c._topic_callbacks["test/topic"]
    c.c.unsubscribe.assert_not_called()


def test_unregister_last_callback_unsubscribes(mocker):
    """Test unregistering the last callback unsubscribes from topic"""
    c = m.Client(None)
    mocker.patch.object(c, "c")
    cb = lambda topic, data: None

    c.c.is_connected.return_value = True
    c.register_topic_callback("test/topic", cb)
    c.unregister_topic_callback("test/topic", cb)
    assert "test/topic" not in c._topic_callbacks
    c.c.unsubscribe.assert_called_once_with("test/topic")


def test_on_connect_resubscribes_callbacks(mocker):
    """Test that on_connect re-subscribes to registered topic callbacks"""
    c = m.Client(None)
    mocker.patch.object(c, "c")
    cb = lambda topic, data: None
    c._topic_callbacks["test/topic"] = [cb]

    c.on_connect(None, None, {}, 0, None)
    c.c.subscribe.assert_any_call("test/topic")


def test_on_message_dispatches_to_callbacks(mocker):
    """Test that on_message dispatches to registered topic callbacks"""
    c = m.Client(None)
    mocker.patch.object(c, "c")

    results = []
    cb = lambda t, d: results.append((t, d))
    c._topic_callbacks["protohaven_api/v1/user/+/signin"] = [cb]

    msg = mocker.MagicMock()
    msg.topic = "protohaven_api/v1/user/123/signin"
    msg.payload = json.dumps({"neon_id": "123"})

    c.on_message(None, None, msg)
    assert len(results) == 1
    assert results[0][0] == "protohaven_api/v1/user/123/signin"
    assert results[0][1] == {"neon_id": "123"}


def test_on_message_callback_error_does_not_crash(mocker):
    """Test that a callback error doesn't crash on_message"""
    c = m.Client(None)
    mocker.patch.object(c, "c")

    def bad_cb(topic, data):
        raise RuntimeError("boom")

    c._topic_callbacks["test/topic"] = [bad_cb]

    msg = mocker.MagicMock()
    msg.topic = "test/topic"
    msg.payload = json.dumps({"foo": "bar"})

    # Should not raise
    c.on_message(None, None, msg)


def test_on_connect_registered_callbacks(mocker):
    """Test on_connect subscribes both default and registered topics"""
    c = m.Client(None)
    mocker.patch.object(c, "c")
    cb = lambda topic, data: None
    c._topic_callbacks["custom/topic"] = [cb]

    c.on_connect(None, None, {}, 0, None)
    c.c.subscribe.assert_any_call("/protohaven_api/v1/notify_discord")
    c.c.subscribe.assert_any_call("custom/topic")
