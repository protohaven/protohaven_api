"""Tests for clearance automation"""

from protohaven_api.automation.membership import clearances as c


def test_update_patch(mocker):
    """Test the update function"""
    mocker.patch.object(
        c.neon,
        "fetch_clearance_codes",
        return_value=[
            {"name": "CLEAR1", "code": "C1", "id": 1},
            {"name": "CLEAR2", "code": "C2", "id": 2},
        ],
    )
    mocker.patch.object(
        c.neon,
        "search_members_by_email",
        return_value=[
            mocker.MagicMock(
                neon_id=123, company_id=456, clearances=["CLEAR1"]
            )
        ],
    )
    mocker.patch.object(
        c.airtable, "get_clearance_to_tool_map", return_value={"MWB": ["ABG", "RBP"]}
    )
    mocker.patch.object(c.neon, "set_clearances", return_value="Success")
    mock_notify = mocker.patch.object(c.mqtt, "notify_clearance")

    assert c.update("a@b.com", "PATCH", ["C2"]) == ["C2"]

    # Note that clearance 1 is still set, since it was set already
    c.neon.set_clearances.assert_called_with(  # pylint: disable=no-member
        123, {2, 1}, is_company=False
    )
    mock_notify.assert_has_calls(
        [
            mocker.call(123, "C2", added=True),
        ],
        any_order=True,
    )
