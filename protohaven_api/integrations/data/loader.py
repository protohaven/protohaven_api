from os import getenv
import logging
import pickle


log = logging.getLogger("integrations.data.loader")

mock_data = {}

if getenv("PH_SERVER_MODE", "dev").lower():
    with open("mock_data.pkl", "rb") as f:
        mock_data = pickle.load(f)
    log.warning(f"Mock data loaded:")
    for k,v in mock_data.items():
        log.warning(f" - {k}: {list(v.keys())}")
