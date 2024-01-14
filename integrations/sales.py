# Select an API and endpoint to get started.

from square.client import Client
from config import get_config

cfg = get_config()['square']
LOCATION = cfg['location']
client = Client(
  access_token=cfg['token'],
  environment="production"
)

def get_cards():
    result = client.cards.list_cards()
    if result.is_success():
      return result.body
    elif result.is_error():
      raise Exception(result.errors)

def get_subscriptions():
    result = client.subscriptions.search_subscriptions(
              body = {}
              )
    if result.is_success():
       return result.body
    elif result.is_error():
       raise Exception(result.errors)

def get_purchases():
    result = client.orders.search_orders(
    body = {
        "location_ids": [LOCATION],
        "query": {
          "filter": {
            "date_time_filter": {
              "created_at": {
                "start_at": "2023-11-15",
                "end_at": "2023-11-30"
              }
            }
          }
        }
      }
    )

    if result.is_success():
      return result.body
    elif result.is_error():
      raise Exception(result.errors)


def get_inventory():
  result = client.inventory.batch_retrieve_inventory_counts()
  if result.is_success():
    return result.body
  elif result.is_error():
    raise Exception(result.errors)
