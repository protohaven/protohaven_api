"""WSGI app construction"""

import logging
from typing import Optional

from flask import Flask  # pylint: disable=import-error
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from protohaven_api.config import get_config
from protohaven_api.handlers.admin import page as admin_pages
from protohaven_api.handlers.auth import page as auth_pages
from protohaven_api.handlers.index import page as index_pages
from protohaven_api.handlers.index import setup_sock_routes as index_ws_setup
from protohaven_api.handlers.instructor import page as instructor_pages
from protohaven_api.handlers.member import page as member_pages
from protohaven_api.handlers.reservations import page as reservations_pages
from protohaven_api.handlers.staff import page as staff_pages
from protohaven_api.handlers.staff import setup_sock_routes as staff_ws_setup
from protohaven_api.handlers.techs import page as techs_pages


def configure_app(
    cookie_domain: str = None,
    behind_proxy: bool = False,
    cors_all_routes: bool = False,
    session_secret: Optional[str] = None,
) -> Flask:
    """Configures the Flask app and returns it"""
    log = logging.getLogger("main")
    app = Flask(__name__)
    if behind_proxy:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    if cors_all_routes:
        log.warning(
            "CORS enabled for all routes - this should be done in dev environments only"
        )
        CORS(app, supports_credentials=True)
    else:
        # We do need CORS for requests hit by our wordpress page.
        protohaven_main = get_config(
            "general/external_urls/protohaven_main", "https://www.protohaven.org"
        )
        assert protohaven_main and protohaven_main != "*"
        CORS(
            app,
            resources={
                r"/event_ticker": {"origins": protohaven_main},
                r"/whoami": {"origins": protohaven_main},
            },
            supports_credentials=True,
        )

    log.info("Registering routes")
    app.secret_key = session_secret
    assert app.secret_key
    app.config["TEMPLATES_AUTO_RELOAD"] = True  # Reload template if signature differs

    # We set the client to forward session data on www as well as api,
    # to allow for logged in session to be detected when browsing classes.
    app.config["SESSION_COOKIE_DOMAIN"] = cookie_domain
    app.config["SESSION_COOKIE_NAME"] = "api_session"
    for p in (
        auth_pages,
        index_pages,
        admin_pages,
        instructor_pages,
        staff_pages,
        techs_pages,
        reservations_pages,
        member_pages,
    ):
        app.register_blueprint(p)

    index_ws_setup(app)
    staff_ws_setup(app)
    return app
