"""A controller/driver for MQTT communications to `protohaven_embedded` devices."""
import json
import logging
import threading
import time
from collections import defaultdict

import paho.mqtt.client as mqtt

from protohaven_api.config import get_config

log = logging.getLogger("integrations.mqtt")

TOPICS = [
    "ERROR",
    "POWER",
    "AUTH",
    "LOCK",
    "MAINT",
    "CONFIG",
    "USERS",
    "RESRV",
    "LOG",
    "ALIVE",
]
SUB_PREFIXES = ("stat", "tele", "err")


class TopicResource:  # pylint: disable=too-few-public-methods
    """Resource names for use in MQTT topics"""

    TOOL = "tool"
    USER = "user"
    SELF = "self"


class TopicAttribute:  # pylint: disable=too-few-public-methods
    """Attribute names for use in MQTT topics"""

    MAINTENANCE = "maint"
    RESERVATION = "resrv"
    HEARTBEAT = "heartbeat"
    SIGNIN = "signin"
    CLEARANCE = "clearance"


class Client:
    """An MQTT client for managing the ShopMinder devices"""

    HEARTBEAT_PD_SEC = 5.0

    def __init__(self):
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.c.on_connect = self.on_connect
        self.c.on_message = self.on_message
        self.c.tls_set(get_config("mqtt/ca_cert_path"))
        self.c.username_pw_set(get_config("mqtt/username"), get_config("mqtt/password"))
        self.c.connect(
            get_config("mqtt/host"),
            get_config("mqtt/port"),
            get_config("mqtt/keepalive_sec"),
        )
        self.shopminders = defaultdict(dict)

    def on_connect(
        self, _, userdata, flags, reason_code, properties
    ):  # pylint:disable=unused-argument
        """Connection update events"""
        log.info(f"Connected with result code {reason_code}")
        log.info(f"Subscribing to {SUB_PREFIXES} on all ShopMinder topics")
        for topic in TOPICS:
            for prefix in SUB_PREFIXES:
                self.c.subscribe(f"{prefix}/+/{topic}")

    def on_message(self, _, userdata, msg):  # pylint:disable=unused-argument
        """Receive messages from MQTT"""
        prefix, minder, topic = [m.strip() for m in msg.topic.split("/")]
        log.info(f"RECV {prefix} {minder} {topic}: {msg.payload}")
        # TODO when device comes online, verify its state and sync any changes since its last connection
        if topic == "ALIVE":
            self._on_shopminder_alive(minder, msg.payload == "1")

    def _on_shopminder_alive(self, name: str, alive: bool):
        self.shopminders[name]["alive"] = alive

    def _on_shopminder_update(self, name: str, attr: str, value):
        pass  # TODO

    def _fmt_topic(self, resource, resource_id, attribute):
        """Constructs topic name based on the type of message being sent"""
        return f"protohaven_api/v1/{resource}/{resource_id}/{attribute}"

    def _pub(self, resource, resource_id, attribute, payload):
        """Publish a message using standard topic formatting"""
        if not isinstance(payload, str):
            payload = json.dumps(payload)
        return self.c.publish(
            self._fmt_topic(resource, resource_id, attribute), payload
        )

    def notify_reservation(self, tool_code, ref, start_time, end_time, user_id):
        """Notify that equipment is being reserved"""
        return self._pub(
            TopicResource.TOOL,
            tool_code,
            TopicAttribute.RESERVATION,
            {"ref": ref, "start": start_time, "end": end_time, "uid": user_id},
        )

    def notify_maintenance(self, tool_code, status, reason):
        """Notify that equipment maintenance status is changing"""
        return self._pub(
            TopicResource.TOOL,
            tool_code,
            TopicAttribute.MAINTENANCE,
            {"status": status, "reason": reason},
        )

    def notify_member_signed_in(self, user_id):
        """Notify that a user has signed in at the front desk"""
        return self._pub(TopicResource.USER, user_id, TopicAttribute.SIGNIN, "1")

    def notify_clearance(self, user_id: str, tool_code: str, added: bool = True):
        """Notify that a user's clearance has been added or removed"""
        return self._pub(
            Topicresource.USER,
            user_id,
            TopicAttribute.CLEARANCE,
            {"tool_code": tool_code, "added": added},
        )

    def _notify_heartbeat(self):
        """A periodic message published to reassure listeners that the server is operational"""
        return self._pub(TopicResource.SELF, "", TopicAttribute.HEARTBEAT, "1")

    def run_forever(self):
        """Starts up dependent threads and loops forever"""
        threading.Thread(target=client.c.loop_forever, daemon=True).start()
        while True:
            time.sleep(self.HEARTBEAT_PD_SEC)
            self._notify_heartbeat()


client = None  # pylint: disable=invalid-name


def run():
    """Run the MQTT client"""
    global client  # pylint: disable=global-statement
    log.info("Initializing MQTT client")
    client = Client()
    client.run_forever()


def get():
    """Gets the client"""
    return client
