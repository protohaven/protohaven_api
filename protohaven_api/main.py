"""Collect various blueprints and start the flask server - also the discord bot"""
import logging
import os

from flask import Flask  # pylint: disable=import-error
from flask_cors import CORS

from protohaven_api.config import get_config
from protohaven_api.discord_bot import run as run_bot
from protohaven_api.handlers.admin import page as admin_pages
from protohaven_api.handlers.auth import page as auth_pages
from protohaven_api.handlers.index import page as index_pages
from protohaven_api.handlers.index import setup_sock_routes
from protohaven_api.handlers.instructor import page as instructor_pages
from protohaven_api.handlers.onboarding import page as onboarding_pages
from protohaven_api.handlers.reservations import page as reservations_pages
from protohaven_api.handlers.techs import page as techs_pages
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.rbac import set_rbac

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
log = logging.getLogger("main")

app = Flask(__name__)
if os.getenv("CORS", "false").lower() == "true":
    log.warning("CORS enabled - this should be done in dev environments only")
    CORS(app)

if os.getenv("UNSAFE_NO_RBAC", "false").lower() == "true":
    log.warning(
        "DANGER DANGER DANGER\n\nRBAC DISABLED; EVERYONE CAN DO EVERYTHING\n\nDANGER DANGER DANGER"
    )
    set_rbac(False)


application = app  # our hosting requires application in passenger_wsgi
cfg = get_config()["general"]
app.secret_key = cfg["session_secret"]
app.config["TEMPLATES_AUTO_RELOAD"] = True  # Reload template if signature differs
for p in (
    auth_pages,
    index_pages,
    admin_pages,
    instructor_pages,
    onboarding_pages,
    techs_pages,
    reservations_pages,
):
    app.register_blueprint(p)

setup_sock_routes(app)

server_mode = os.getenv("PH_SERVER_MODE", "dev").lower()
run_discord_bot = os.getenv("DISCORD_BOT", "false").lower() == "true"
init_connector(dev=server_mode != "prod")
if run_discord_bot:
    import threading

    t = threading.Thread(target=run_bot, daemon=True)
    t.start()

else:
    log.warning("Skipping startup of discord bot")

if __name__ == "__main__":
    app.run()
