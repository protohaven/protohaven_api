"""Test of sales integration module"""

from protohaven_api.integrations import sales as s


def test_get_unpaid_invoices_by_id(mocker):
    """Test fetching unpaid invoices keyed by ID"""
    mock_invoices = [
        {"id": "inv1", "invoice_number": "001", "status": "UNPAID"},
        {"id": "inv2", "invoice_number": "002", "status": "PAID"},
        {"id": "inv3", "invoice_number": "003", "status": "PARTIALLY_PAID"},
    ]
    mock_result = mocker.Mock()
    mock_result.is_success.return_value = True
    mock_result.body = {"invoices": mock_invoices}

    mocker.patch.object(s, "client")
    mock_client_instance = mocker.Mock()
    mock_client_instance.invoices.list_invoices.return_value = mock_result
    s.client.return_value = mock_client_instance

    got = dict(s.get_unpaid_invoices_by_id())
    expected = {"inv1": "001", "inv3": "003"}
    assert got == expected
