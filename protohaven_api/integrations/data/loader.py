"""Logic for loading mock data based on PH_SERVER_MODE env"""
import logging
import os
import pickle

log = logging.getLogger("integrations.data.loader")

_mock_data = {}


def mock_data():
    """Fetches mock data (if any was loaded)"""
    return _mock_data


MOCK_DATA_PATH = "mock_data.pkl"

if os.getenv("PH_SERVER_MODE", "dev").lower() == "dev":
    if os.path.isfile(MOCK_DATA_PATH):
        with open(MOCK_DATA_PATH, "rb") as f:
            _mock_data = pickle.load(f)
        log.warning("Mock data loaded:")
        for k, v in _mock_data.items():
            log.warning(f" - {k}: {list(v.keys())}")
    else:
        log.warning(
            "PH_SERVER_MODE indicates dev, but mock data NOT loaded,"
            + "path %s not found",
            MOCK_DATA_PATH,
        )
