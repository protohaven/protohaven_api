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


def test_get_subscriptions_paginates_with_cursor_in_body(mocker):
    """Subsequent subscription searches must send the cursor in the body"""
    page_1 = mocker.Mock()
    page_1.is_success.return_value = True
    page_1.body = {"subscriptions": [{"id": "sub1"}], "cursor": "next-page"}

    page_2 = mocker.Mock()
    page_2.is_success.return_value = True
    page_2.body = {"subscriptions": [{"id": "sub2"}]}

    mocker.patch.object(s, "client")
    mock_client_instance = mocker.Mock()
    mock_client_instance.subscriptions.search_subscriptions.side_effect = [
        page_1,
        page_2,
    ]
    s.client.return_value = mock_client_instance

    got = list(s.get_subscriptions())

    assert got == [{"id": "sub1"}, {"id": "sub2"}]
    assert mock_client_instance.subscriptions.search_subscriptions.call_args_list == [
        mocker.call(body={}),
        mocker.call(body={"cursor": "next-page"}),
    ]
