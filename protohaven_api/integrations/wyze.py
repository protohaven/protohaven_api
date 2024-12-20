"""Simple integration with Wyze security systems"""
import logging

from wyze_sdk import Client
from wyze_sdk.models.devices import Camera, ContactSensor

from protohaven_api.config import get_config

log = logging.getLogger("integrations.wyze")

cli = None  # pylint: disable=invalid-name


def init():
    """Initializes the client"""
    # Need to do get_config('wyze/expiration') warning. Automate renewal?
    global cli  # pylint: disable=global-statement
    cli = Client()
    rep = cli.login(
        email=get_config("wyze/email"),
        password=get_config("wyze/password"),
        key_id=get_config("wyze/key_id"),
        api_key=get_config("wyze/api_key"),
    )
    return rep


def get_door_states():
    """Gets the states of all doors in the shop"""
    for d in cli.devices_list():
        if d.product.type == ContactSensor.type:
            yield {
                "name": d.nickname,
                "mac": d.mac,
                "is_online": d.is_online,
                "open_close_state": d.open_close_state,
            }


def get_camera_states():
    """Gets the states of all cameras in the shop"""
    for d in cli.devices_list():
        if d.product.type == Camera.type:
            yield {"name": d.nickname, "mac": d.mac, "is_online": d.is_online}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log.info("Initializing")
    init()
    for s in get_door_states():
        log.info(f"{s}")
