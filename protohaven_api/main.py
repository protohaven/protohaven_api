"""Collect various blueprints and start the flask server - also the discord bot"""

import logging
import threading

from protohaven_api.app import configure_app
from protohaven_api.automation.membership.sign_in import initialize as init_signin
from protohaven_api.automation.roles.roles import setup_discord_user
from protohaven_api.config import get_config
from protohaven_api.integrations import airtable, booked, mqtt, neon, tasks
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.integrations.data.dev_connector import DevConnector
from protohaven_api.integrations.discord_bot import run as run_bot
from protohaven_api.rbac import set_rbac

logging.basicConfig(level=get_config("general/log_level").upper())
log = logging.getLogger("main")
log.info("Creating flask server")

server_mode = get_config("general/server_mode").lower()

app = configure_app(
    cookie_domain=".protohaven.org" if server_mode == "prod" else ".localhost",
    behind_proxy=get_config("general/behind_proxy", as_bool=True),
    cors_all_routes=get_config("general/cors", as_bool=True),
    session_secret=get_config("general/session_secret"),
)

if get_config("general/unsafe/no_rbac", as_bool=True):
    log.warning(
        "DANGER DANGER DANGER\n\nRBAC DISABLED; EVERYONE CAN DO EVERYTHING\n\nDANGER DANGER DANGER"
    )
    set_rbac(False)

log.info(f"Initializing connector ({server_mode})")
init_connector(Connector if server_mode == "prod" else DevConnector)

# Create Asana webhook for purchase requests if enabled
# Webhook creation will be handled in a delayed thread after server starts

log.info("Initializing sign-in precaching")
# Must run after connector is initialized; prefetches from Neon/Airtable
if get_config("general/precache_sign_in", as_bool=True):
    neon.cache.start()
    airtable.cache.start()
    booked.cache.start(delay=60.0 if server_mode == "prod" else 0)
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
    log.debug(f"Reservation cache by tool: {rr}")
    for tool_code, data in rr.items():
        neon_id = neon.cache.neon_id_from_booked_id(int(data["user"]))
        log.info(f"Reservation: {tool_code} {neon_id} {data}")
        mqtt.notify_reservation(
            tool_code,
            data["ref"],
            data["start"],
            data["end"],
            neon_id,
        )


if get_config("booked/notify_mqtt", as_bool=True):
    booked.cache.cb = _on_reservations
else:
    log.warning("Skipping periodic post of tool reservations to MQTT")

def create_asana_webhook_if_enabled():
    """Create Asana webhook for purchase requests if enabled in config."""
    try:
        # Check if webhook is enabled
        is_enabled = get_config(
            "asana/webhooks/purchase_requests/enabled", default=False, as_bool=True
        )
        if not is_enabled:
            log.info("Purchase requests webhook disabled in config")
            return
        
        # Determine target URL based on server mode
        if server_mode == "prod":
            target_url = "https://api.protohaven.org/admin/asana_webhook"
        else:
            target_url = get_config(
                "asana/webhooks/purchase_requests/target_url",
                default="http://localhost:5000/admin/asana_webhook",
            )
        
        log.info(f"Ensuring Asana webhook exists for purchase requests at {target_url}")
        webhook_gid = tasks.ensure_purchase_requests_webhook(target_url)
        if webhook_gid:
            log.info(f"Purchase requests webhook ensured: {webhook_gid}")
        else:
            log.warning("Failed to ensure purchase requests webhook")
    except Exception as e:
        log.error(f"Error creating Asana webhook: {e}")


if __name__ == "__main__":
    log.info("Entering run loop")
    
    # Start webhook creation in a background thread after a short delay
    # This gives the server time to start before Asana sends verification request
    import threading
    import time
    
    def delayed_webhook_creation():
        # Wait for server to be ready
        time.sleep(5)
        create_asana_webhook_if_enabled()
    
    webhook_thread = threading.Thread(target=delayed_webhook_creation, daemon=True)
    webhook_thread.start()
    
    app.run()
