"""Square point of sale integration for Protohaven"""

from functools import cache

from protohaven_api.config import get_config
from protohaven_api.integrations.data.connector import get as get_connector

cfg = get_config()["square"]
LOCATION = cfg["location"]


@cache
def client():
    """Gets the square client via the connector module"""
    return get_connector().square_client()


def get_cards():
    """Get all credit cards on file"""
    result = client().cards.list_cards()
    if result.is_success():
        return result.body
    raise RuntimeError(result.errors)


def get_subscriptions():
    """Get all subscriptions - these are commonly used for storage"""
    result = client().subscriptions.search_subscriptions(body={})
    if result.is_success():
        return result.body
    raise RuntimeError(result.errors)


def get_purchases():
    """Get all purchases - usually snacks and consumables from the front store"""
    result = client().orders.search_orders(
        body={
            "location_ids": [LOCATION],
            "query": {
                "filter": {
                    "date_time_filter": {
                        "created_at": {"start_at": "2023-11-15", "end_at": "2023-11-30"}
                    }
                }
            },
        }
    )

    if result.is_success():
        return result.body
    raise RuntimeError(result.errors)


def get_inventory():
    """Get all inventory"""
    result = (
        client().inventory.batch_retrieve_inventory_counts()  # pylint: disable=no-value-for-parameter
    )
    if result.is_success():
        return result.body
    raise RuntimeError(result.errors)
