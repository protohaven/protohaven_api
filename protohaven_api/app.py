"""WSGI app construction"""
import logging

from flask import Flask  # pylint: disable=import-error
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

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


def configure_app(behind_proxy=False, cors_all_routes=False, session_secret=None):
    """Configures the Flask app and returns it"""
    log = logging.getLogger("main")
    app = Flask(__name__)
    if behind_proxy:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    if cors_all_routes:
        log.warning(
            "CORS enabled for all routes - this should be done in dev environments only"
        )
        CORS(app)
    else:
        # We do need CORS for requests hit by our wordpress page.
        CORS(
            app, resources={r"/event_ticker": {"origins": "https://www.protohaven.org"}}
        )

    log.info("Registering routes")
    app.secret_key = session_secret
    assert app.secret_key
    app.config["TEMPLATES_AUTO_RELOAD"] = True  # Reload template if signature differs
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
