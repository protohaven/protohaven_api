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
from typing import Any, Dict, Optional

from flask import Flask, Response, jsonify, request

from protohaven_api.config import get_config
from protohaven_api.integrations import neon
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.integrations.data.dev_connector import DevConnector
from protohaven_api.integrations.models import Member

log = logging.getLogger("cache_server")

server_mode: str = get_config("general/server_mode").lower()

# Module-level app for gunicorn (created lazily so tests can mock first)
app: Optional[Flask] = None  # pylint: disable=invalid-name


def _serialize_member(member: Member) -> Dict[str, Any]:
    """Serialize a Member object to its raw dataclass fields.

    Returns the underlying dataclass fields (neon_raw_data, neon_search_data,
    neon_membership_data, airtable_bio_data) so the Member can be fully
    reconstructed on the client side via Member(**data).
    """
    return {
        "neon_raw_data": member.neon_raw_data,
        "neon_search_data": member.neon_search_data,
        "neon_membership_data": member.neon_membership_data,
        "airtable_bio_data": member.airtable_bio_data,
    }


def create_app() -> Flask:
    """Create and configure the cache server Flask app.

    Also sets the module-level `app` for gunicorn compatibility.
    """
    global app  # pylint: disable=global-statement

    fapp: Flask = Flask(__name__)

    # Initialize connector so AccountCache can make Neon API calls on cache miss
    log.info("Initializing connector (%s)", server_mode)
    init_connector(Connector if server_mode == "prod" else DevConnector)
    neon.cache.start()
    log.info("AccountCache started for cache_server")

    @fapp.route("/find_best_match")
    def find_best_match() -> tuple[Response, int] | Response:
        """Fuzzy-search for members by name/email.

        Query params:
            search: The search string (required)
            top_n: Max results to return (default 10)
            score_cutoff: Minimum fuzzy match score 0-100 (default 65)
        """
        search: str = request.args.get("search", "")
        if not search:
            return jsonify({"error": "search parameter is required"}), 400

        top_n: int = int(request.args.get("top_n", 10))
        score_cutoff: int = int(request.args.get("score_cutoff", 65))

        results: list[Dict[str, Any]] = []
        for member in neon.cache.find_best_match(
            search, top_n=top_n, score_cutoff=score_cutoff
        ):
            results.append(_serialize_member(member))

        return jsonify(results)

    @fapp.route("/get")
    def get_member() -> tuple[Response, int] | Response:
        """Look up members by email.

        Query params:
            key: The email address to look up (required)
            fetch_if_missing: Whether to fall back to Neon API on cache miss
                              (default "1", set to "0" to disable)
        """
        key: str = request.args.get("key", "")
        if not key:
            return jsonify({"error": "key parameter is required"}), 400

        fetch_if_missing: bool = request.args.get("fetch_if_missing", "1") != "0"
        data: Dict[str, Member] = neon.cache.get(
            key, {}, fetch_if_missing=fetch_if_missing
        )
        result: Dict[str, Dict[str, Any]] = {}
        for neon_id, member in data.items():
            result[neon_id] = _serialize_member(member)

        return jsonify(result)

    app = fapp
    return fapp


if __name__ == "__main__":
    logging.basicConfig(level=get_config("general/log_level", "INFO").upper())
    application: Flask = create_app()
    port: int = int(get_config("cache_server/port", 5001))  # pylint: disable=invalid-name
    log.info("Starting cache server on port %s", port)
    application.run(host="0.0.0.0", port=port)
