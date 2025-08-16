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

from protohaven_api.integrations.ldap_service import create_ldap_service


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the LDAP server."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
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
        """
    )
    
    parser.add_argument(
        "--host", 
        default="0.0.0.0", 
        help="Host to bind the LDAP server to (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=3891, 
        help="Port to bind the LDAP server to (default: 3891)"
    )
    
    parser.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run in test mode (don't start actual server, just validate setup)"
    )
    
    return parser.parse_args()


def signal_handler(signum, frame, ldap_service=None) -> NoReturn:
    """Handle shutdown signals gracefully."""
    logger = logging.getLogger("ldap_server")
    logger.info(f"Received signal {signum}, shutting down...")
    
    if ldap_service:
        ldap_service.stop_server()
    
    logger.info("LDAP server shutdown complete")
    sys.exit(0)


def run_server(host: str, port: int, test_mode: bool = False) -> int:
    """Run the LDAP server."""
    logger = logging.getLogger("ldap_server")
    
    try:
        # Create and start the LDAP service
        logger.info("Creating LDAP service")
        ldap_service = create_ldap_service(host=host, port=port)
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, ldap_service))
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, ldap_service))
        
        # Start the service
        if not ldap_service.start_server():
            logger.error("Failed to start LDAP service")
            return 1
        
        # Health check
        health = ldap_service.health_check()
        logger.info(f"Service health check: {health}")
        
        if test_mode:
            logger.info("Test mode - stopping service")
            ldap_service.stop_server()
            return 0
        
        logger.info("LDAP server is running. Press Ctrl+C to stop.")
        
        # Keep the server running
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
    args = parse_args()
    
    setup_logging(args.log_level)
    logger = logging.getLogger("ldap_server")
    
    logger.info(f"Starting Neon CRM LDAP Proxy Server")
    logger.info(f"Host: {args.host}, Port: {args.port}")
    logger.info(f"Test mode: {args.test_mode}")
    
    return run_server(args.host, args.port, args.test_mode)


if __name__ == "__main__":
    sys.exit(main())
