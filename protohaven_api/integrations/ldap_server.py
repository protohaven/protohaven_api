#!/usr/bin/env python3
"""Standalone LDAP server runner for Neon CRM integration with Pocket ID.

This script can be run independently to start an LDAP service that proxies
account data from Neon CRM, suitable for integration with Pocket ID.

Usage:
    python -m protohaven_api.integrations.ldap_server [--host HOST] [--port PORT]

Or directly:
    python protohaven_api/integrations/ldap_server.py [--host HOST] [--port PORT]
"""

import argparse
import logging
import signal
import sys
import time
from typing import NoReturn

from protohaven_api.integrations import neon
from protohaven_api.integrations.ldap_service import create_ldap_service


def signal_handler(signum, frame, ldap_service=None) -> NoReturn:
    """Handle shutdown signals gracefully."""
    logger = logging.getLogger("ldap_server")
    logger.info(f"Received signal {signum}, shutting down...")

    if ldap_service:
        ldap_service.stop_server()

    logger.info("LDAP server shutdown complete")
    sys.exit(0)


def run_server(host: str, port: int) -> int:
    """Run the LDAP server."""
    logger = logging.getLogger("ldap_server")

    try:
        logger.info("Starting AccountCache")
        neon.cache.start()
        logger.info("Creating LDAP service")
        ldap_service = create_ldap_service(host=host, port=port)
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, ldap_service))
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, ldap_service))

        if not ldap_service.start_server():
            logger.error("Failed to start LDAP service")
            return 1

        health = ldap_service.health_check()
        logger.info(f"Service health check: {health}")
        logger.info("LDAP server is running. Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(1)

                # Periodic health check (every 5 minutes)
                if int(time.time()) % 300 == 0:
                    health = ldap_service.health_check()
                    logger.debug(f"Periodic health check: {health}")

        except KeyboardInterrupt:
            signal_handler(signal.SIGINT, None, ldap_service)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


def main() -> int:
    """Main entry point for the LDAP server."""
    parser = argparse.ArgumentParser(
        description="Neon CRM LDAP Proxy Server for Pocket ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This service creates an LDAP interface to Neon CRM member data, suitable
for integration with Pocket ID or other LDAP-based authentication systems.

The service will:
- Cache active member data from Neon CRM
- Provide LDAP search and authentication interfaces
- Map Neon member fields to standard LDAP attributes
- Refresh member data periodically (every 5 minutes)

Configuration:
Ensure your environment has proper Neon CRM API credentials configured.
Optionally set LDAP base DN via config: ldap/base_dn
        """,
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the LDAP server to (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=3891,
        help="Port to bind the LDAP server to (default: 3891)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger("ldap_server")
    logger.info(f"Starting Neon CRM LDAP Proxy Server")
    logger.info(f"Host: {args.host}, Port: {args.port}")

    return run_server(args.host, args.port)


if __name__ == "__main__":
    sys.exit(main())
