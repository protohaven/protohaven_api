"""Mock implementation of Square integration using Nocodb"""

from protohaven_api.integrations import airtable_base


class Response:  # pylint: disable=too-few-public-methods
    """A successful response"""

    def __init__(self, body):
        self.body = body

    def is_success(self):
        """Returns true"""
        return True


class Customers:  # pylint: disable=too-few-public-methods
    """Mock customer data"""

    def list_customers(self, cursor=None):  # pylint: disable=unused-argument
        """Returns customer list info"""
        result = []
        for rec in airtable_base.get_all_records("fake_square", "customers"):
            if rec["fields"].get("Data"):
                result.append(rec["fields"]["Data"])
        return Response({"customers": result})


class Catalog:  # pylint: disable=too-few-public-methods
    """Mock catalog data"""

    def list_catalog(self, cursor=None, types=None):  # pylint: disable=unused-argument
        """Returns subscription plan info"""
        assert types == "SUBSCRIPTION_PLAN_VARIATION"
        result = []
        for rec in airtable_base.get_all_records("fake_square", "subscription_plans"):
            if rec["fields"].get("Data"):
                result.append(rec["fields"]["Data"])
        return Response({"objects": result})


class Subscriptions:  # pylint: disable=too-few-public-methods
    """Mock subscription data"""

    def search_subscriptions(
        self, body=None, cursor=None
    ):  # pylint: disable=unused-argument
        """Searches subscriptions"""
        result = []
        for rec in airtable_base.get_all_records("fake_square", "subscriptions"):
            if rec["fields"].get("Data"):
                result.append(rec["fields"]["Data"])
        return Response({"subscriptions": result})

    def update_subscription(self, subscription_id, note):
        """Set the note section of the subscription"""
        assert isinstance(note, str)
        assert subscription_id
        for rec in airtable_base.get_all_records("fake_square", "subscriptions"):
            data = rec["fields"].get("Data")
            if data and data["id"] == subscription_id:
                data["note"] = note
                status, content = airtable_base.update_record(
                    {"Data": data}, "fake_square", "subscriptions", rec["id"]
                )
                if status != 200:
                    raise RuntimeError(f"{status}: {content}")
                return Response(content)
        raise RuntimeError("Subscription not found")


class Invoices:  # pylint: disable=too-few-public-methods
    """Mock invoice data"""

    def get_invoice(self, inv_id):
        """Gets invoice by ID"""
        for rec in airtable_base.get_all_records("fake_square", "invoices"):
            d = rec["fields"].get("Data")
            if d and d["id"] == inv_id:
                return Response({"invoice": d})
        return RuntimeError("Invoice not found")

    def list_invoices(self, _):
        """Gets a list of all invoices - we ignore location because there's only one"""
        result = []
        for rec in airtable_base.get_all_records("fake_square", "invoices"):
            d = rec["fields"].get("Data")
            if d:
                result.append(d)
        return Response({"invoices": result})


class Client:
    """Mock implementation of Wyze API client"""

    def __init__(self):
        pass

    @property
    def subscriptions(self):
        """Gets all subscriptions"""
        return Subscriptions()

    @property
    def catalog(self):
        """Gets subscription class"""
        return Catalog()

    @property
    def customers(self):
        """Gets customer list"""
        return Customers()

    @property
    def invoices(self):
        """Gets invoices list"""
        return Invoices()
