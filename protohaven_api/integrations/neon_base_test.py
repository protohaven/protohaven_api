# pylint: disable=protected-access
"""Test base methods for neon integration"""

import datetime
import json

import pytest

from protohaven_api.integrations import neon_base as nb


def _neo(mocker):
    """Create a NeonOne without relying on a real TOTP secret"""
    mocker.patch.object(nb.pyotp, "TOTP")
    return nb.NeonOne()


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


def test_paginated_search_removes_duplicate_output_fields(mocker):
    """Test paginated_search removes duplicates from output fields which would cause a Neon error"""
    mock_connector = mocker.patch.object(nb, "get_connector")
    m = mock_connector.return_value.neon_request
    m.side_effect = [
        {"pagination": {"totalPages": 1}, "searchResults": [{"id": 1}]},
    ]
    list(nb.paginated_search([], ["a", "a", 123, 123]))
    m.assert_called_once()
    output_fields = json.loads(m.call_args_list[0].kwargs["data"])["outputFields"]
    assert len(output_fields) == 2 and 123 in output_fields and "a" in output_fields


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
    """Test that paginated_fetch raises RuntimeError when search fails"""
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
    assert not nb.fetch_account("123").is_company()

    # Test case where neon_request returns a company account
    m.return_value = {"companyAccount": {"a": 1}}
    assert nb.fetch_account("123").is_company()


def test_patch_account(mocker):
    """Test patching an account with Neon V2 API"""
    mock_acct = mocker.MagicMock()
    mock_acct.is_company.return_value = False
    fa = mocker.patch.object(nb, "fetch_account", return_value=mock_acct)
    p = mocker.patch.object(nb, "patch", return_value={"success": True})

    test_data = {"name": "Test User"}
    got = nb.patch_account("acc_123", test_data)

    fa.assert_called_once_with("acc_123", required=True)
    p.assert_called_once_with(
        "api_key2", "/accounts/acc_123", {"individualAccount": test_data}
    )
    assert got == {"success": True}


def test_paginated_fetch_batching(mocker):
    """Batching mode yields one page at a time instead of individual records"""
    mocker.patch.object(nb, "get_connector")
    mocker.patch.object(
        nb.get_connector(),
        "neon_request",
        return_value={"pagination": {"totalPages": 1}, "foo": [{"id": 1}, {"id": 2}]},
    )
    assert list(nb.paginated_fetch("api_key1", "/foo", batching=True)) == [
        [{"id": 1}, {"id": 2}]
    ]


def test_paginated_fetch_skips_empty_page(mocker):
    """Empty pages yield no records but still advance"""
    mocker.patch.object(nb, "get_connector")
    m = mocker.patch.object(
        nb.get_connector(),
        "neon_request",
        return_value={"pagination": {"totalPages": 1}, "foo": []},
    )
    assert not list(nb.paginated_fetch("api_key1", "/foo"))
    m.assert_called_once()


def test_fetch_account_raw(mocker):
    """raw=True returns the Neon response directly"""
    content = {"individualAccount": {"a": 1}}
    mocker.patch.object(nb, "get", return_value=content)
    member = mocker.patch.object(nb.Member, "from_neon_fetch")
    assert nb.fetch_account("123", raw=True) == content
    member.assert_not_called()


def test_fetch_account_with_memberships(mocker):
    """A truthy/callable fetch_memberships argument populates membership data"""
    content = {"individualAccount": {"a": 1}}
    mocker.patch.object(nb, "get", return_value=content)
    member = mocker.MagicMock()
    mocker.patch.object(nb.Member, "from_neon_fetch", return_value=member)
    mocker.patch.object(
        nb, "fetch_memberships_internal_do_not_call_directly", return_value=[1, 2]
    )
    got = nb.fetch_account("123", fetch_memberships=lambda m: True)
    assert got == member
    member.set_membership_data.assert_called_once_with([1, 2])


def test_put_post_delete(mocker):
    """put/post/delete issue requests with the expected method and JSON body"""
    mocker.patch.object(nb, "get_connector")
    m = mocker.patch.object(nb.get_connector(), "neon_request")
    nb.put("api_key2", "/accounts/1", {"a": 1})
    nb.post("api_key2", "/accounts/1", {"a": 2})
    nb.delete("api_key2", "/accounts/1")
    assert [c.kwargs["data"] for c in m.call_args_list[:2]] == [
        json.dumps({"a": 1}),
        json.dumps({"a": 2}),
    ]
    assert [c.args[1] for c in m.call_args_list] == ["PUT", "POST", "DELETE"]


def test_extract_custom_field():
    """Custom fields return either value or optionValues, defaulting to []"""
    acc = {
        "accountCustomFields": [
            {"id": "1", "value": "x"},
            {"id": "2", "optionValues": ["a", "b"]},
        ]
    }
    assert nb.extract_custom_field(acc, 1) == "x"
    assert nb.extract_custom_field(acc, 2) == ["a", "b"]
    assert nb.extract_custom_field(acc, 3) == []


def test_set_custom_fields(mocker):
    """List values become optionValues; scalars become value"""
    pa = mocker.patch.object(nb, "patch_account")
    nb.set_custom_fields("acc", ("1", ["a"]), ("2", "b"))
    pa.assert_called_once_with(
        "acc",
        {
            "accountCustomFields": [
                {"id": "1", "optionValues": ["a"]},
                {"id": "2", "value": "b"},
            ]
        },
        None,
    )


def test_duplicate_request_token(mocker):
    """Token starts at current time and increments on get"""
    mocker.patch.object(nb.time, "time", return_value=100)
    drt = nb.DuplicateRequestToken()
    assert drt.i == 100
    assert drt.get() == 101
    assert drt.get() == 102


def test_neon_one_do_login(mocker):
    """do_login fills the expected login and MFA forms"""
    neo = _neo(mocker)
    mocker.patch.object(neo.totp, "now", return_value="123456")
    page = mocker.MagicMock()
    locator = mocker.MagicMock()
    page.locator.return_value = locator

    neo.do_login(page)

    page.goto.assert_called_once_with("https://app.neoncrm.com/np/ssoAuth")
    assert page.fill.call_args_list[0].args == ("input[name='email']", mocker.ANY)
    locator.click.assert_called_once()
    assert page.fill.call_args_list[1].args == ("input[name='password']", mocker.ANY)
    assert page.fill.call_args_list[2].args == ("input[name='mfa_code']", "123456")
    assert page.click.call_count == 2


def test_create_single_use_abs_event_discounts(mocker):
    """Playwright context is set up and one discount is posted per code"""
    neo = _neo(mocker)
    mock_sp = mocker.patch.object(nb, "sync_playwright")
    p = mocker.MagicMock()
    browser = mocker.MagicMock()
    page = mocker.MagicMock()
    mock_sp.return_value.__enter__.return_value = p
    p.firefox.launch.return_value = browser
    browser.new_page.return_value = page
    mocker.patch.object(nb.NeonOne, "do_login")
    post = mocker.patch.object(
        nb.NeonOne, "_post_discount", side_effect=["CODE1", "CODE2"]
    )

    got = list(neo.create_single_use_abs_event_discounts(["CODE1", "CODE2"], 25))

    assert got == ["CODE1", "CODE2"]
    assert post.call_count == 2
    browser.close.assert_called_once()


def test_create_single_use_abs_event_discounts_retries_login(mocker):
    """A login timeout triggers a second login attempt"""
    neo = _neo(mocker)
    mock_sp = mocker.patch.object(nb, "sync_playwright")
    p = mocker.MagicMock()
    browser = mocker.MagicMock()
    page = mocker.MagicMock()
    mock_sp.return_value.__enter__.return_value = p
    p.firefox.launch.return_value = browser
    browser.new_page.return_value = page
    login = mocker.patch.object(
        nb.NeonOne,
        "do_login",
        side_effect=[nb.PlaywrightTimeoutError("timeout"), None],
    )
    mocker.patch.object(nb, "time")
    mocker.patch.object(nb.NeonOne, "_post_discount")

    list(neo.create_single_use_abs_event_discounts(["CODE1"], 25))

    assert login.call_count == 2


def test_post_discount_success(mocker):
    """_post_discount fills the coupon form and returns the code"""
    neo = _neo(mocker)
    page = mocker.MagicMock()
    page.get_by_text.return_value.is_visible.return_value = True

    got = neo._post_discount(
        page,
        None,
        "CODE",
        False,
        25,
        from_date=datetime.datetime(2025, 1, 1),
        to_date=datetime.datetime(2025, 4, 1),
    )

    assert got == "CODE"
    assert page.fill.call_count == 5
    page.click.assert_called_once_with("input[type='submit']")


def test_post_discount_rejects_percent_discounts(mocker):
    """_post_discount currently only supports absolute discounts"""
    neo = _neo(mocker)
    page = mocker.MagicMock()
    with pytest.raises(AssertionError):
        neo._post_discount(
            page,
            None,
            "CODE",
            True,
            25,
            from_date=datetime.datetime(2025, 1, 1),
            to_date=datetime.datetime(2025, 4, 1),
        )


def test_post_discount_missing_code_on_result_page(mocker):
    """Raises if the submitted code does not appear after redirect"""
    neo = _neo(mocker)
    page = mocker.MagicMock()
    page.get_by_text.return_value.is_visible.return_value = False
    with pytest.raises(RuntimeError, match="code not found"):
        neo._post_discount(
            page,
            None,
            "CODE",
            False,
            25,
            from_date=datetime.datetime(2025, 1, 1),
            to_date=datetime.datetime(2025, 4, 1),
        )
