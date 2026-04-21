"""A controller/driver for MQTT communications to `protohaven_embedded` devices."""

import json
import logging
import socket
import threading
import time

import paho.mqtt.client as mqtt

from protohaven_api.config import get_config

log = logging.getLogger("integrations.mqtt")


class TopicResource:  # pylint: disable=too-few-public-methods
    """Resource names for use in MQTT topics"""

    TOOL = "tool"
    USER = "user"
    SELF = "self"
    ACTION = "action"


class TopicAttribute:  # pylint: disable=too-few-public-methods
    """Attribute names for use in MQTT topics"""

    MAINTENANCE = "maint"
    RESERVATION = "resrv"
    HEARTBEAT = "heartbeat"
    SIGNIN = "signin"
    CLEARANCE = "clearance"


class Client:
    """An MQTT client for managing shop signals"""

    HEARTBEAT_PD_SEC = 5.0

    def __init__(self, notify_discord_cb):
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.notify_discord_cb = notify_discord_cb

    def _start(self):
        self.c.on_connect = self.on_connect
        self.c.on_message = self.on_message
        cert_path = get_config("mqtt/ca_cert_path").strip()
        if cert_path != "":
            self.c.tls_set(cert_path)
        self.c.username_pw_set(get_config("mqtt/username"), get_config("mqtt/password"))
        self.c.connect(
            get_config("mqtt/host"),
            get_config("mqtt/port"),
            get_config("mqtt/keepalive_sec"),
        )

    def on_connect(
        self, _, userdata, flags, reason_code, properties
    ):  # pylint:disable=unused-argument
        """Connection update events"""
        log.info(f"Connected with result code {reason_code}")
        for sub in ("/protohaven_api/v1/notify_discord",):
            self.c.subscribe(sub)
            log.info(f"Subscribed to {sub}")

    def on_message(self, _, userdata, msg):  # pylint:disable=unused-argument
        """Receive messages from MQTT"""
        log.info(f"RECV {msg.topic}: {msg.payload[:128]}...")
        try:
            data = json.loads(msg.payload)
        except json.JSONDecodeError:
            log.warning("Failed to decode message; ignoring")
            return

        if msg.topic == "/protohaven_api/v1/notify_discord":
            if not data.get("channel") or not data.get("message"):
                log.error("`channel` and `message` required for discord notiication")
            else:
                self.notify_discord_cb(data["message"], data["channel"], blocking=False)

    def _fmt_topic(self, resource, resource_id, attribute):
        """Constructs topic name based on the type of message being sent"""
        return f"protohaven_api/v1/{resource}/{resource_id}/{attribute}"

    def pub(self, resource, resource_id, attribute, payload):
        """Publish a message using standard topic formatting"""
        if not isinstance(payload, str):
            payload = json.dumps(payload)
        return self.c.publish(
            self._fmt_topic(resource, resource_id, attribute), payload
        )

    def _notify_heartbeat(self):
        """A periodic message published to reassure listeners that the server is operational"""
        return self.pub(
            TopicResource.SELF, socket.gethostname(), TopicAttribute.HEARTBEAT, "1"
        )

    def run_forever(self):
        """Starts up dependent threads and loops forever"""
        self._start()
        threading.Thread(target=client.c.loop_forever, daemon=True).start()
        while True:
            time.sleep(self.HEARTBEAT_PD_SEC)
            self._notify_heartbeat()


client = None  # pylint: disable=invalid-name


def run(notify_discord_cb):
    """Run the MQTT client"""
    global client  # pylint: disable=global-statement
    log.info("Initializing MQTT client")
    client = Client(notify_discord_cb)
    client.run_forever()


def get():
    """Gets the client"""
    return client


def notify_reservation(tool_code, ref, start_time, end_time, user_id):
    """Notify that equipment is being reserved"""
    if not client:
        return None
    return client.pub(
        TopicResource.TOOL,
        tool_code,
        TopicAttribute.RESERVATION,
        {
            "ref": ref,
            "start": start_time,
            "end": end_time,
            "uid": user_id,
        },
    )


def notify_maintenance(tool_code, status, reason):
    """Notify that equipment maintenance status is changing"""
    if not client:
        return None
    return client.pub(
        TopicResource.TOOL,
        tool_code,
        TopicAttribute.MAINTENANCE,
        {"status": status, "reason": reason},
    )


def notify_member_signed_in(user_id):
    """Notify that a user has signed in at the front desk"""
    if not client:
        return None
    return client.pub(TopicResource.USER, user_id, TopicAttribute.SIGNIN, "1")


def notify_clearance(user_id: str, tool_code: str, added: bool = True):
    """Notify that a user's clearance has been added or removed"""
    if not client:
        return None
    return client.pub(
        TopicResource.TOOL,
        tool_code,
        TopicAttribute.CLEARANCE,
        {"uid": user_id, "added": added, "level": "MEMBER"},
    )
