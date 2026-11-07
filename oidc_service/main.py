"""Run the standalone Protohaven OIDC service."""

import logging
import os

from oidc_service.app import create_app
from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import Connector
from protohaven_api.integrations.data.connector import init as init_connector
from protohaven_api.integrations.data.dev_connector import DevConnector

logging.basicConfig(level=get_config("general/log_level", "INFO").upper())
log = logging.getLogger("oidc_service")

SERVER_MODE = str(get_config("general/server_mode", "dev")).lower()
log.info("Initializing Neon connector in %s mode", SERVER_MODE)
init_connector(Connector if SERVER_MODE == "prod" else DevConnector)

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5002"))
    app.run(host="0.0.0.0", port=port)
