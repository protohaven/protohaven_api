"""A controller/driver for MQTT communications to `protohaven_embedded` devices."""

import datetime
import json
import logging
import socket
import threading
import time
from collections import defaultdict

import paho.mqtt.client as mqtt

from protohaven_api.config import get_config, tznow
from protohaven_api.integrations import airtable, booked, neon

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


class ClearanceLevel:  # pylint: disable=too-few-public-methods
    """Levels of auth/clearance for a tool, for shopminder"""

    MEMBER = "MEMBER"
    TECH = "TECH"
    ADMIN = "ADMIN"


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


client = None  # pylint: disable=invalid-name


def notify_maintenance(tool_code, status, reason):
    """Notify that equipment maintenance status is changing"""
    return client.pub(
        TopicResource.TOOL,
        tool_code,
        TopicAttribute.MAINTENANCE,
        {"status": status, "reason": reason},
    )


def notify_member_signed_in(user_id):
    """Notify that a user has signed in at the front desk"""
    return client.pub(TopicResource.USER, user_id, TopicAttribute.SIGNIN, "1")


def notify_clearance(
    user_id: str, tool_code: str, added: bool = True, level=ClearanceLevel.MEMBER
):
    """Notify that a user's clearance has been added or removed"""
    return client.pub(
        TopicResource.TOOL,
        tool_code,
        TopicAttribute.CLEARANCE,
        {"uid": user_id, "added": added, "level": level},
    )


class Client:
    """An MQTT client for managing the ShopMinder devices"""

    HEARTBEAT_PD_SEC = 5.0

    def __init__(self):
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.shopminders = defaultdict(dict)
        self.next_notify = {}

    def _start(self):
        self.c.on_connect = self.on_connect
        self.c.on_message = self.on_message
        self.c.tls_set(get_config("mqtt/ca_cert_path"))
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
        log.info(f"Subscribing to {SUB_PREFIXES} on all ShopMinder topics")
        for topic in TOPICS:
            for prefix in SUB_PREFIXES:
                self.c.subscribe(f"{prefix}/+/{topic}")

    def on_message(self, _, userdata, msg):  # pylint:disable=unused-argument
        """Receive messages from MQTT"""
        prefix, minder, topic = [m.strip() for m in msg.topic.split("/")]
        log.info(f"RECV {prefix} {minder} {topic}: {msg.payload}")
        if topic == "ALIVE":
            self._on_shopminder_alive(minder, msg.payload == "1")

    def _on_shopminder_alive(self, name: str, alive: bool):
        self.shopminders[name]["alive"] = alive

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

    def _on_interval(self, fn, sec):
        now = tznow()
        if self.next_notify.get(fn.__name__, now) > now:
            return
        fn()
        self.next_notify[fn.__name__] = now + datetime.timedelta(seconds=sec)
        log.debug(f"Next notification for {fn.__name__}: {sec}s")

    def _notify_reservations(self):
        rr = booked.cache.get_today_reservations_by_tool()
        for tool_code, data in rr.items():
            neon_id = neon.cache.neon_id_from_booked_id(data["user"])
            log.info(f"Reservation: {tool_code} {neon_id} {data}")
            self.pub(
                TopicResource.TOOL,
                tool_code,
                TopicAttribute.RESERVATION,
                {
                    "ref": data["ref"],
                    "start": data["start"],
                    "end": data["end"],
                    "uid": neon_id,
                },
            )

    def _notify_maintenance(self):
        for tool_code, data in airtable.tool_cache.all_tool_statuses().items():
            log.info(f"Maint: {tool_code} {data}")
            self.pub(TopicResource.TOOL, tool_code, TopicAttribute.MAINTENANCE, data)

    def _notify_clearance(self):
        for tool_code, neon_ids in neon.cache.member_clearances().items():
            for neon_id in neon_ids:
                self.pub(
                    TopicResource.TOOL, tool_code, TopicAttribute.CLEARANCE, neon_id
                )

    def _notify_signins(self):
        log.info("TODO notify signin")

    def run_forever(self):
        """Starts up dependent threads and loops forever"""
        self._start()
        threading.Thread(target=client.c.loop_forever, daemon=True).start()
        intervals = get_config("mqtt/publish_interval_sec")
        while True:
            time.sleep(1)
            self._on_interval(self._notify_heartbeat, intervals["heartbeat"])
            self._on_interval(self._notify_reservations, intervals["reservations"])
            self._on_interval(self._notify_maintenance, intervals["maintenance"])
            self._on_interval(self._notify_clearance, intervals["clearance"])
            self._on_interval(self._notify_signins, intervals["signins"])


def run():
    """Run the MQTT client"""
    global client  # pylint: disable=global-statement
    log.info("Initializing MQTT client")
    client = Client()
    client.run_forever()


def get():
    """Gets the client"""
    return client
