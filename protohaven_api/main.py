"""Collect various blueprints and start the flask server - also the discord bot"""

import logging

from flask import Flask  # pylint: disable=import-error
from flask_cors import CORS

from protohaven_api.config import get_config
from protohaven_api.discord_bot import run as run_bot
from protohaven_api.handlers.admin import page as admin_pages
from protohaven_api.handlers.auth import page as auth_pages
from protohaven_api.handlers.index import page as index_pages
from protohaven_api.handlers.index import setup_sock_routes as index_ws_setup
from protohaven_api.handlers.instructor import page as instructor_pages
from protohaven_api.handlers.member import page as member_pages
from protohaven_api.handlers.onboarding import page as onboarding_pages
from protohaven_api.handlers.reservations import page as reservations_pages
from protohaven_api.handlers.staff import page as staff_pages
from protohaven_api.handlers.staff import setup_sock_routes as staff_ws_setup
from protohaven_api.handlers.techs import page as techs_pages
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.integrations.data.dev_connector import DevConnector
from protohaven_api.rbac import set_rbac

cfg = get_config()

logging.basicConfig(level=cfg["general"]["log_level"].upper())
log = logging.getLogger("main")

app = Flask(__name__)
if cfg["general"]["behind_proxy"]:
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

if cfg["general"]["cors"].lower() == "true":
    log.warning("CORS enabled - this should be done in dev environments only")
    CORS(app)

if cfg["general"]["unsafe_no_rbac"].lower() == "true":
    log.warning(
        "DANGER DANGER DANGER\n\nRBAC DISABLED; EVERYONE CAN DO EVERYTHING\n\nDANGER DANGER DANGER"
    )
    set_rbac(False)


application = app  # our hosting requires application in passenger_wsgi
app.secret_key = cfg["general"]["session_secret"]
app.config["TEMPLATES_AUTO_RELOAD"] = True  # Reload template if signature differs
for p in (
    auth_pages,
    index_pages,
    admin_pages,
    instructor_pages,
    onboarding_pages,
    staff_pages,
    techs_pages,
    reservations_pages,
    member_pages,
):
    app.register_blueprint(p)

index_ws_setup(app)
staff_ws_setup(app)

server_mode = cfg["general"]["server_mode"].lower()
run_discord_bot = cfg["discord_bot"]["enabled"].lower() == "true"
init_connector(Connector if server_mode == "prod" else DevConnector)
if run_discord_bot:
    import threading

    from protohaven_api.role_automation.roles import (  # pylint: disable=ungrouped-imports
        setup_discord_user,
    )

    t = threading.Thread(target=run_bot, daemon=True, args=(setup_discord_user,))
    t.start()

else:
    log.warning("Skipping startup of discord bot")

if __name__ == "__main__":
    app.run()
