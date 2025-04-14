"""Simple integration with Wyze security systems"""

import logging

from protohaven_api.integrations.data.connector import get as get_connector

log = logging.getLogger("integrations.wyze")


def get_door_states():
    """Gets the states of all doors in the shop"""
    for d in get_connector().wyze_client().entry_sensors.list():
        yield {
            "name": d.nickname,
            "mac": d.mac,
            "is_online": d.is_online,
            "open_close_state": d.open_close_state,
        }


def get_camera_states():
    """Gets the states of all cameras in the shop"""
    for d in get_connector().wyze_client().cameras.list():
        yield {"name": d.nickname, "mac": d.mac, "is_online": d.is_online}
