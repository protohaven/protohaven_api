"""Test base methods for neon integration"""

import pytest

from protohaven_api.integrations import neon_base as nb


def test_paginated_search(mocker):
    """Test paginated account search to ensure all pages are requested and results are aggregated"""
    mock_connector = mocker.patch.object(nb, "get_connector")
    m = mock_connector.return_value.neon_request
    m.side_effect = [
        {"pagination": {"totalPages": 2}, "searchResults": [{"id": 1}]},
        {"pagination": {"totalPages": 2}, "searchResults": [{"id": 2}]},
    ]
    results = list(nb.paginated_search([], []))
    assert results == [{"id": 1}, {"id": 2}]
    assert m.call_count == 2


def test_paginated_search_runtime_error(mocker):
    """Test that paginated_search raises RuntimeError when search fails"""
    mock_connector = mocker.patch.object(nb, "get_connector")
    m = mock_connector.return_value.neon_request
    m.side_effect = [{"pagination": {"totalPages": 2}, "searchResults": None}]
    with pytest.raises(RuntimeError, match="Search failed"):
        list(nb.paginated_search([], []))


def test_paginated_fetch(mocker):
    """Test paginated account search to ensure all pages are requested and results are aggregated"""
    mocker.patch.object(nb, "get_connector")
    m = mocker.patch.object(
        nb.get_connector(),
        "neon_request",
        side_effect=[
            {"pagination": {"totalPages": 2}, "foo": [{"id": 1}]},
            {"pagination": {"totalPages": 2}, "foo": [{"id": 2}]},
        ],
    )
    results = list(nb.paginated_fetch("api_key1", "/foo", {"a": 1}))
    assert results == [{"id": 1}, {"id": 2}]
    m.assert_has_calls(
        [
            mocker.call(
                mocker.ANY, "GET", "https://api.neoncrm.com/v2/foo?a=1&currentPage=0"
            ),
            mocker.call(
                mocker.ANY, "GET", "https://api.neoncrm.com/v2/foo?a=1&currentPage=1"
            ),
        ]
    )


def test_paginated_fetch_runtime_error(mocker):
    """Test that paginated_search raises RuntimeError when search fails"""
    mocker.patch.object(nb, "get_connector")
    mocker.patch.object(
        nb.get_connector(), "neon_request", return_value=["Error: testing error"]
    )
    with pytest.raises(RuntimeError, match="testing error"):
        list(nb.paginated_fetch("api_key1", "/foo"))


def test_fetch_account(mocker):
    """Test various conditions of calling `fetch_account`"""
    mocker.patch.object(nb, "get_connector")
    m = mocker.patch.object(nb.get_connector(), "neon_request")
    # Test case where neon_request returns a list (error case)
    m.return_value = ["error"]
    with pytest.raises(RuntimeError, match="error"):
        nb.fetch_account("123")

    # Test case where neon_request returns None and required is True
    m.return_value = None
    with pytest.raises(RuntimeError, match="Account not found: 123"):
        nb.fetch_account("123", required=True)

    # Test case where neon_request returns None and required is False
    m.return_value = None
    assert nb.fetch_account("123", required=False) is None

    # Test case where neon_request returns an individual account
    m.return_value = {"individualAccount": {"a": 1}}
    assert nb.fetch_account("123") == ({"a": 1}, False)

    # Test case where neon_request returns a company account
    m.return_value = {"companyAccount": {"a": 1}}
    assert nb.fetch_account("123") == ({"a": 1}, True)


def test_do_login(mocker):
    """Tests the login flow with 2-factor auth"""

    mock_session = mocker.MagicMock()
    mock_session.post.side_effect = [
        mocker.Mock(
            status_code=200,
            content=b'2-Step Verification name="_token" value="mfa_token"',
        ),
        mocker.Mock(content=b"Log Out", status_code=200),
    ]
    mock_session.get.return_value = mocker.Mock(
        content=b"Mission Control Dashboard", status_code=200
    )

    mocker.patch.object(
        nb,
        "get_connector",
        return_value=mocker.MagicMock(neon_session=lambda: mock_session),
    )

    n = nb.NeonOne(autologin=False)
    assert n.s == mock_session

    mocker.patch.object(n, "_get_csrf", return_value="dummy_csrf")
    mocker.patch.object(n, "totp", mocker.Mock(now=lambda: "123456"))

    n.do_login("user", "pass")

    mock_session.post.assert_any_call(
        "https://app.neonsso.com/login",
        data={
            "_token": "dummy_csrf",
            "email": "user",
            "password": "pass",  # pragma: allowlist secret
        },
    )
    mock_session.post.assert_any_call(
        "https://app.neonsso.com/mfa",
        data={"_token": "mfa_token", "mfa_code": "123456"},
    )
    mock_session.get.assert_called_once_with("https://app.neoncrm.com/np/ssoAuth")
