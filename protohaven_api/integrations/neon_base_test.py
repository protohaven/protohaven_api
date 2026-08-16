# pylint: disable=protected-access
"""Test base methods for neon integration"""

import datetime
import json

import pytest

from protohaven_api.integrations import neon_base as nb
from protohaven_api.testing import d


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


def test_get_ticket_groups_from_content(mocker):
    """Ticket groups are parsed from the admin event details HTML"""
    neo = _neo(mocker)
    html = (
        '<td class="ticket-group"><font>General</font>'
        '<a href="ticketGroupId=123&amp;foo=bar">x</a></td>'
    )
    assert neo.get_ticket_groups(None, "evt", content=html) == {"General": "123"}


def test_get_ticket_groups_from_request(mocker):
    """When content is omitted, event details are fetched from the admin context"""
    neo = _neo(mocker)
    ctx = mocker.MagicMock()
    html = '<td class="ticket-group"><font>General</font>ticketGroupId=42&</td>'
    ctx.request.get.return_value.text.return_value = html
    assert neo.get_ticket_groups(ctx, "evt") == {"General": "42"}
    ctx.request.get.assert_called_once()


def test_create_ticket_group_req_success(mocker):
    """Creates a ticket group with duplicate request token"""
    neo = _neo(mocker)
    mocker.patch.object(nb.DuplicateRequestToken, "get", return_value=42)
    ctx = mocker.MagicMock()
    rg = mocker.MagicMock()
    rg.status = 200
    rg.url = "http://example.com/ref"
    r = mocker.MagicMock()
    r.status = 200
    ctx.request.get.return_value = rg
    ctx.request.post.return_value = r

    got = neo.create_ticket_group_req_(ctx, "evt", "Group", "Desc")

    assert got == r
    ctx.request.post.assert_called_once()
    assert (
        ctx.request.post.call_args.kwargs["form"]["ticketPackageGroup.groupName"]
        == "Group"
    )
    assert ctx.request.post.call_args.kwargs["form"]["z2DuplicateRequestToken"] == 42


def test_create_ticket_group_req_error(mocker):
    """Non-200 response from savePackageGroup.do is reported"""
    neo = _neo(mocker)
    ctx = mocker.MagicMock()
    rg = mocker.MagicMock()
    rg.status = 200
    rg.url = "http://example.com/ref"
    r = mocker.MagicMock()
    r.status = 500
    r.text.return_value = "boom"
    ctx.request.get.return_value = rg
    ctx.request.post.return_value = r
    with pytest.raises(RuntimeError, match="500: boom"):
        neo.create_ticket_group_req_(ctx, "evt", "Group", "Desc")


def test_assign_conditions_to_group_success(mocker):
    """Successful condition assignment returns True"""
    neo = _neo(mocker)
    ctx = mocker.MagicMock()
    r = mocker.MagicMock()
    r.status = 200
    r.json.return_value = {"success": True}
    ctx.request.post.return_value = r
    assert neo.assign_conditions_to_group(ctx, "42", [{}]) is True


def test_assign_conditions_to_group_error(mocker):
    """Report filter errors are surfaced"""
    neo = _neo(mocker)
    ctx = mocker.MagicMock()
    r = mocker.MagicMock()
    r.status = 500
    ctx.request.post.return_value = r
    with pytest.raises(RuntimeError, match="Report filter edit failed"):
        neo.assign_conditions_to_group(ctx, "42", [{}])


def test_assign_price_to_group_success(mocker):
    """Successful price assignment returns True"""
    neo = _neo(mocker)
    mocker.patch.object(nb.DuplicateRequestToken, "get", return_value=42)
    ctx = mocker.MagicMock()
    ag = mocker.MagicMock()
    ag.text.return_value = "Event Price"
    ag.url = "http://example.com/ref"
    r = mocker.MagicMock()
    r.status = 302
    r.text.return_value = "<html></html>"
    ctx.request.get.return_value = ag
    ctx.request.post.return_value = r

    assert neo.assign_price_to_group(ctx, "evt", "42", "Price", 25, 3) is True
    assert ctx.request.post.call_args.kwargs["form"]["z2DuplicateRequestToken"] == 42


def test_assign_price_to_group_error(mocker):
    """Non-302 response or page errors are surfaced"""
    neo = _neo(mocker)
    ctx = mocker.MagicMock()
    ag = mocker.MagicMock()
    ag.text.return_value = "Event Price"
    ag.url = "http://example.com/ref"
    r = mocker.MagicMock()
    r.status = 200
    r.text.return_value = "<html></html>"
    ctx.request.get.return_value = ag
    ctx.request.post.return_value = r
    with pytest.raises(RuntimeError, match="Price creation failed"):
        neo.assign_price_to_group(ctx, "evt", "42", "Price", 25, 3)


def test_upsert_ticket_group_default(mocker):
    """Default group is returned without hitting the admin site"""
    neo = _neo(mocker)
    ctx = mocker.MagicMock()
    assert neo.upsert_ticket_group(ctx, "evt", "default", "") == "default"
    ctx.assert_not_called()


def test_upsert_ticket_group_creates_missing_group(mocker):
    """Missing groups are created and then looked up again"""
    neo = _neo(mocker)
    ctx = mocker.MagicMock()
    mocker.patch.object(
        neo,
        "get_ticket_groups",
        side_effect=[{"Other": "456"}, {"General": "789"}],
    )
    create = mocker.patch.object(neo, "create_ticket_group_req_")
    create.return_value.text.return_value = "<html>new group</html>"
    assert neo.upsert_ticket_group(ctx, "evt", "General", "desc") == "789"
    create.assert_called_once_with(ctx, "evt", "General", "desc")


def test_delete_all_prices_and_groups(mocker):
    """Prices and groups are deleted, then the first price is deleted again"""
    neo = _neo(mocker)
    ctx = mocker.MagicMock()
    html = (
        "deletePackage.do?eventId=7&id=10 "
        "deletePackage.do?eventId=7&id=11 "
        "ticketGroupId=20 ticketGroupId=21"
    )
    ctx.request.get.return_value.text.return_value = html
    neo.delete_all_prices_and_groups(ctx, "7")
    urls = [c.args[0] for c in ctx.request.get.call_args_list]
    assert any("deletePackage.do?eventId=7&id=10" in u for u in urls)
    assert any("deletePackage.do?eventId=7&id=11" in u for u in urls)
    assert any("deletePackageGroup.do" in u and "ticketGroupId=20" in u for u in urls)
    assert any("deletePackageGroup.do" in u and "ticketGroupId=21" in u for u in urls)
    assert urls[-1].endswith("deletePackage.do?eventId=7&id=10")


def test_delete_all_prices_and_groups_requires_event(mocker):
    """Empty event IDs are rejected"""
    neo = _neo(mocker)
    with pytest.raises(AssertionError):
        neo.delete_all_prices_and_groups(None, "")


def test_assign_pricing(mocker):
    """assign_pricing logs in, clears pricing, and assigns every configured price"""
    neo = _neo(mocker)
    mock_sp = mocker.patch.object(nb, "sync_playwright")
    p = mocker.MagicMock()
    browser = mocker.MagicMock()
    ctx = mocker.MagicMock()
    page = mocker.MagicMock()
    mock_sp.return_value.__enter__.return_value = p
    p.firefox.launch.return_value = browser
    browser.new_context.return_value = ctx
    ctx.new_page.return_value = page
    mocker.patch.object(nb.NeonOne, "do_login")
    clear = mocker.patch.object(nb.NeonOne, "delete_all_prices_and_groups")
    upsert = mocker.patch.object(nb.NeonOne, "upsert_ticket_group")
    cond = mocker.patch.object(nb.NeonOne, "assign_conditions_to_group")
    price = mocker.patch.object(nb.NeonOne, "assign_price_to_group")

    neo.assign_pricing("evt", 100, 10, clear_existing=True)

    clear.assert_called_once_with(ctx, "evt")
    assert upsert.call_count == len(nb.pricing)
    assert cond.call_count == len([p for p in nb.pricing if p.get("cond")])
    assert price.call_count == len(nb.pricing)


def test_assign_pricing_include_discounts_false(mocker):
    """include_discounts=False only assigns the default price"""
    neo = _neo(mocker)
    mock_sp = mocker.patch.object(nb, "sync_playwright")
    p = mocker.MagicMock()
    browser = mocker.MagicMock()
    ctx = mocker.MagicMock()
    page = mocker.MagicMock()
    mock_sp.return_value.__enter__.return_value = p
    p.firefox.launch.return_value = browser
    browser.new_context.return_value = ctx
    ctx.new_page.return_value = page
    mocker.patch.object(nb.NeonOne, "do_login")
    upsert = mocker.patch.object(nb.NeonOne, "upsert_ticket_group")
    cond = mocker.patch.object(nb.NeonOne, "assign_conditions_to_group")
    price = mocker.patch.object(nb.NeonOne, "assign_price_to_group")

    neo.assign_pricing("evt", 100, 10, include_discounts=False)

    upsert.assert_called_once()
    cond.assert_not_called()
    price.assert_called_once()


def test_delete_event_unsafe(mocker):
    """delete_event_unsafe calls the Neon delete API"""
    delete = mocker.patch.object(nb, "delete", return_value="ok")
    assert nb.delete_event_unsafe("evt") == "ok"
    delete.assert_called_once_with("api_key3", "/events/evt")
    with pytest.raises(AssertionError):
        nb.delete_event_unsafe("")


def test_create_event_dry_run():
    """dry_run logs the event and returns None"""
    assert nb.create_event("Name", "Desc", d(0, 10), d(0, 12), dry_run=True) is None


def test_create_event_live(mocker):
    """A live event is POSTed to Neon and its ID is returned"""
    mocker.patch.object(nb, "get_connector")
    m = mocker.patch.object(
        nb.get_connector(), "neon_request", return_value={"id": "evt1"}
    )
    got = nb.create_event("Name", "Desc", d(0, 10), d(0, 12), dry_run=False)
    assert got == "evt1"
    assert m.call_args.args[1] == "POST"
    assert json.loads(m.call_args.kwargs["data"])["name"] == "Name"
