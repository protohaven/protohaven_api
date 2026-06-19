"""
Standalone Flask server exposing AccountCache methods over HTTP.

Intended to be run as a separate process so caching can be scaled
independently from the main Flask application.

Endpoints:
  GET /find_best_match?search=...&top_n=10&score_cutoff=65
  GET /get?key=<email>

Usage:
  python -m protohaven_api.cache_server
  gunicorn protohaven_api.cache_server:app
"""

import logging

from flask import Flask, jsonify, request

from protohaven_api.config import get_config
from protohaven_api.integrations import neon
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector

log = logging.getLogger("cache_server")

# Module-level app for gunicorn (created lazily so tests can mock first)
app = None  # pylint: disable=invalid-name


def _serialize_member(member):
    """Serialize a Member object to a JSON-compatible dict.

    Uses neon_search_data as the primary source since that is what
    AccountCache stores after refresh. Falls back to computed properties
    where needed.
    """
    return {
        "neon_id": member.neon_id,
        "fname": member.fname,
        "lname": member.lname,
        "email": member.email,
        "name": member.name,
        "account_current_membership_status": (
            member.account_current_membership_status
        ),
        "membership_level": member.membership_level,
        "neon_search_data": member.neon_search_data,
    }


def create_app():
    """Create and configure the cache server Flask app.

    Also sets the module-level `app` for gunicorn compatibility.
    """
    global app  # pylint: disable=global-statement

    fapp = Flask(__name__)

    # Initialize connector so AccountCache can make Neon API calls on cache miss
    init_connector(Connector)
    neon.cache.start()
    log.info("AccountCache started for cache_server")

    @fapp.route("/find_best_match")
    def find_best_match():
        """Fuzzy-search for members by name/email.

        Query params:
            search: The search string (required)
            top_n: Max results to return (default 10)
            score_cutoff: Minimum fuzzy match score 0-100 (default 65)
        """
        search = request.args.get("search", "")
        if not search:
            return jsonify({"error": "search parameter is required"}), 400

        top_n = int(request.args.get("top_n", 10))
        score_cutoff = int(request.args.get("score_cutoff", 65))

        results = []
        for member in neon.cache.find_best_match(
            search, top_n=top_n, score_cutoff=score_cutoff
        ):
            results.append(_serialize_member(member))

        return jsonify(results)

    @fapp.route("/get")
    def get_member():
        """Look up members by email.

        Query params:
            key: The email address to look up (required)
        """
        key = request.args.get("key", "")
        if not key:
            return jsonify({"error": "key parameter is required"}), 400

        data = neon.cache.get(key, {})
        result = {}
        for neon_id, member in data.items():
            result[neon_id] = _serialize_member(member)

        return jsonify(result)

    app = fapp
    return fapp


if __name__ == "__main__":
    logging.basicConfig(
        level=get_config("general/log_level", "INFO").upper()
    )
    application = create_app()
    port = int(get_config("cache_server/port", 5001))  # pylint: disable=invalid-name
    log.info("Starting cache server on port %s", port)
    application.run(host="0.0.0.0", port=port)
