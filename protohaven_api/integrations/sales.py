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


def get_invoice(invoice_id):
    """Fetch the details of a specific invoice by its id"""
    result = client().invoices.get_invoice(invoice_id)
    if result.is_success():
        return result.body["invoice"]
    raise RuntimeError(result.errors)


def subscription_tax_pct(sub, price):
    """Compute the tax percentage for a given subscription. Note that only
    some subscriptions have the `tax_percentage` field, others must be computed
    from linked invoices"""
    assert price >= 0.000000001

    if sub.get("tax_percentage"):
        return float(sub["tax_percentage"])

    # Not having a tax_percentage field doesn't guarantee it has no tax.
    # We have to inspect the latest invoice and work backwards from the charge.
    if len(sub["invoice_ids"]) == 0:
        return 0.0  # Not charged, not taxed

    inv = get_invoice(sub["invoice_ids"][0])  # 0 is most recent
    amt = inv["payment_requests"][0]["computed_amount_money"]["amount"]
    return 100 * ((amt / price) - 1.0)


def get_subscription_plan_map():
    """Get available subscription options, mapped by ID to type"""
    data = client().catalog.list_catalog(types="SUBSCRIPTION_PLAN_VARIATION")
    if not data.is_success():
        raise RuntimeError(data.errors)

    result = {}
    for v in data.body["objects"]:
        if not v["is_deleted"]:
            name = v["subscription_plan_variation_data"]["name"]
            price = v["subscription_plan_variation_data"]["phases"][0]["pricing"][
                "price"
            ]["amount"]
            result[v["id"]] = (name, price)
    return result


def get_customer_name_map():
    """Get full list of customers, mapping ID to name"""

    data = {}
    result = client().customers.list_customers()
    while result:
        if not result.is_success():
            raise RuntimeError(result.errors)
        for v in result.body["customers"]:
            given = v.get("given_name", "")
            family = v.get("family_name", "")
            nick = v.get("nickname")
            email = v.get("email_address")
            fmt = f"{given} {family}"
            if nick:
                fmt += f"({nick})"
            if email:
                fmt += f" {email}"
            data[v["id"]] = fmt
        if result.body.get("cursor"):
            result = client().customers.list_customers(cursor=result.body["cursor"])
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


def get_inventory():
    """Get all inventory"""
    result = (
        client().inventory.batch_retrieve_inventory_counts()  # pylint: disable=no-value-for-parameter
    )
    if result.is_success():
        return result.body
    raise RuntimeError(result.errors)
