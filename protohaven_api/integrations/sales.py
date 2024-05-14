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

def get_subscription_plan_map():
    """Get available subscription options, mapped by ID to type"""
    result = client().catalog.list_catalog()
    if result.is_success():
        return {
                v['id']: v['subscription_plan_variation_data']['name']
            for v in result.body['objects'] if v['type'] == 'SUBSCRIPTION_PLAN_VARIATION' and not v['is_deleted']
            }
    raise RuntimeError(result.errors)


def get_customer_name_map():
    """Get full list of customers, mapping ID to name"""

    data = {}
    result = client().customers.list_customers()
    while result:
        if not result.is_success():
            raise RuntimeError(result.errors)
        for v in result.body['customers']:
            given = v.get('given_name', '')
            family = v.get('family_name', '')
            nick = v.get('nickname')
            email = v.get('email_address')
            fmt = f"{given} {family}"
            if nick:
                fmt += f"({nick})"
            if email: 
                fmt += f" {email}"
            data[v['id']] = fmt
        if result.body.get('cursor'):
            result = client().customers.list_customers(cursor=result.body['cursor'])
        else:
            return data
    return data

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

26
def get_inventory():
    """Get all inventory"""
    result = (
        client().inventory.batch_retrieve_inventory_counts()  # pylint: disable=no-value-for-parameter
    )
    if result.is_success():
        return result.body
    raise RuntimeError(result.errors)
