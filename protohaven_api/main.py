"""Collect various blueprints and start the flask server - also the discord bot"""

import logging
import threading

from flask import Flask  # pylint: disable=import-error
from flask_cors import CORS

from protohaven_api.automation.membership.sign_in import initialize as init_signin
from protohaven_api.automation.roles.roles import setup_discord_user
from protohaven_api.config import get_config
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
from protohaven_api.integrations.discord_bot import run as run_bot
from protohaven_api.rbac import set_rbac

logging.basicConfig(level=get_config("general/log_level").upper())
log = logging.getLogger("main")

app = Flask(__name__)
if get_config("general/behind_proxy", as_bool=True):
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

if get_config("general/cors", as_bool=True):
    log.warning(
        "CORS enabled for all routes - this should be done in dev environments only"
    )
    CORS(app)
else:
    # We do need CORS for requests hit by our wordpress page.
    CORS(app, resources={r"/event_ticker": {"origins": "https://www.protohaven.org"}})

if get_config("general/unsafe_no_rbac", as_bool=True):
    log.warning(
        "DANGER DANGER DANGER\n\nRBAC DISABLED; EVERYONE CAN DO EVERYTHING\n\nDANGER DANGER DANGER"
    )
    set_rbac(False)


application = app  # our hosting requires application in passenger_wsgi
app.secret_key = get_config("general/session_secret")
assert app.secret_key
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

server_mode = get_config("general/server_mode").lower()
init_connector(Connector if server_mode == "prod" else DevConnector)

if __name__ == "__main__":
    app.run()

    # Must run after connector is initialized; prefetches from Neon/Airtable
    if get_config("general/precache_sign_in", as_bool=True):
        init_signin()

    if get_config("discord_bot/enabled", as_bool=True):
        t = threading.Thread(target=run_bot, daemon=True, args=(setup_discord_user,))
        t.start()

    else:
        log.warning("Skipping startup of discord bot")
