"""Collect various blueprints and start the flask server - also the discord bot"""

import logging
import threading

from protohaven_api.app import configure_app
from protohaven_api.automation.membership.sign_in import initialize as init_signin
from protohaven_api.automation.roles.roles import setup_discord_user
from protohaven_api.config import get_config
from protohaven_api.integrations import airtable, mqtt, neon
from protohaven_api.integrations.booked import ReservationCache
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.integrations.data.dev_connector import DevConnector
from protohaven_api.integrations.discord_bot import run as run_bot
from protohaven_api.rbac import set_rbac

logging.basicConfig(level=get_config("general/log_level").upper())
log = logging.getLogger("main")
log.info("Creating flask server")

app = configure_app(
    behind_proxy=get_config("general/behind_proxy", as_bool=True),
    cors_all_routes=get_config("general/cors", as_bool=True),
    session_secret=get_config("general/session_secret"),
)

if get_config("general/unsafe/no_rbac", as_bool=True):
    log.warning(
        "DANGER DANGER DANGER\n\nRBAC DISABLED; EVERYONE CAN DO EVERYTHING\n\nDANGER DANGER DANGER"
    )
    set_rbac(False)

server_mode = get_config("general/server_mode").lower()

log.info(f"Initializing connector ({server_mode})")
init_connector(Connector if server_mode == "prod" else DevConnector)

log.info("Initializing sign-in precaching")
# Must run after connector is initialized; prefetches from Neon/Airtable
if get_config("general/precache_sign_in", as_bool=True):
    neon.cache.start()
    airtable.cache.start()
    init_signin()

if get_config("discord_bot/enabled", as_bool=True):
    threading.Thread(target=run_bot, daemon=True, args=(setup_discord_user,)).start()
else:
    log.warning("Skipping startup of discord bot")

if get_config("mqtt/enabled", as_bool=True):
    threading.Thread(target=mqtt.run, daemon=True).start()
else:
    log.warning("Skipping startup of mqtt client")


def _on_reservations(cache):
    rr = cache.get_today_reservations_by_tool()
    log.info(f"Reservation cache by tool: {rr}")
    for tool_code, data in rr.items():
        neon_id = neon.cache.neon_id_from_booked_id(data["user"])
        log.info(f"Reservation: {tool_code} {neon_id} {data}")
        mqtt.notify_reservation(
            tool_code,
            data["ref"],
            data["start"],
            data["end"],
            neon_id,
        )


rc = ReservationCache(_on_reservations)
if get_config("booked/notify_mqtt", as_bool=True):
    rc.start(delay=60.0)
else:
    log.warning("Skipping periodic post of tool reservations to MQTT")

if __name__ == "__main__":
    log.info("Entering run loop")
    app.run()
