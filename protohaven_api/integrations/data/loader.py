"""Logic for loading mock data based on PH_SERVER_MODE env"""
import logging
import pickle
from os import getenv

log = logging.getLogger("integrations.data.loader")

mock_data = {}

if getenv("PH_SERVER_MODE", "dev").lower():
    with open("mock_data.pkl", "rb") as f:
        mock_data = pickle.load(f)
    log.warning("Mock data loaded:")
    for k, v in mock_data.items():
        log.warning(f" - {k}: {list(v.keys())}")
