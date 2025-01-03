"""Unit tests for Booked API integration"""

from dateutil.parser import parse as parse_date

from protohaven_api.integrations import booked


def test_get_resource_map(mocker):
    """Basic test of `get_resource_map`, that it calls out and returns mapped values"""
    mocker.patch.object(booked, "get_connector")
    booked.get_connector().booked_request.return_value = {
        "resources": [
            {"customAttributes": [{"id": 3, "value": "ABC"}], "resourceId": 123}
        ]
    }
    mocker.patch.object(booked, "get_config", return_value=3)
    assert booked.get_resource_map() == {"ABC": 123}


def test_get_resource_singleton(mocker):
    """Basic test of get_resource() to fetch a Booked resource"""
    mocker.patch.object(booked, "get_connector")
    booked.get_resource("test_id")
    booked.get_connector().booked_request.assert_called_once_with(  # pylint: disable=no-member
        "GET", "/Resources/test_id"
    )


def test_get_reservations(mocker):
    """Ensure the correct URL is formed when checking reservations"""
    mocker.patch.object(booked, "get_connector")
    booked.get_reservations(parse_date("2024-01-01"), parse_date("2024-02-02"))
    booked.get_connector().booked_request.assert_called_once_with(  # pylint: disable=no-member
        "GET",
        "/Reservations/?startDateTime=2024-01-01T00:00:00&endDateTime=2024-02-02T00:00:00",  # pylint: disable=line-too-long
    )


def test_reserve_resource(mocker):
    """Ensure data is properly formatted when submitting a reservation"""
    mocker.patch.object(booked, "get_connector")
    booked.reserve_resource(123, parse_date("2024-01-01"), parse_date("2024-01-02"))
    booked.get_connector().booked_request.assert_called_once_with(  # pylint: disable=no-member
        "POST",
        "/Reservations/",
        json={
            "description": "api.protohaven.org reservation",
            "endDateTime": "2024-01-02T00:00:00",
            "resourceId": 123,
            "startDateTime": "2024-01-01T00:00:00",
            "title": "System Reserved",
            "userId": 103,  # a specific "robot" user, configured in Booked
        },
    )


def test_apply_resource_custom_fields(mocker):
    """Test that custom fields are merged on existing fields"""
    mocker.patch.object(booked, "get_connector")
    mocker.patch.object(booked, "get_resource")
    booked.get_resource.return_value = {
        "customAttributes": [{"id": 3, "value": "ABC"}],
        "resourceId": 123,
    }
    booked.apply_resource_custom_fields(123, area="Foo")
    booked.get_connector().booked_request.assert_called_once_with(  # pylint: disable=no-member
        "POST",
        "/Resources/123",
        json={
            "customAttributes": [
                {"attributeId": 3, "attributeValue": "ABC"},
                {"attributeId": 2, "attributeValue": "Foo"},
            ],
            "resourceId": 123,
        },
    )


def test_stage_tool_update(mocker):
    """Test updating a tool's metadata"""
    mocker.patch.object(
        booked,
        "get_config",
        side_effect=lambda k: {
            "booked/resource_custom_attribute": {"attr": "123"},
            "booked/tool_type_id": 1,
        }[k],
    )

    r = {
        "statusId": booked.STATUS_UNAVAILABLE,
        "typeId": "0",
        # Yes, the API uses different key names for fecthing state
        # ("id"/"value") vs patching state ("attributeId", "attributeValue")
        "customAttributes": [{"id": "123", "value": "old_value"}],
    }
    r2, changes = booked.stage_tool_update(
        r, {"attr": "new_value"}, reservable=True, additional="info"
    )

    assert r2["statusId"] == booked.STATUS_AVAILABLE
    assert r2["typeId"] == "1"
    assert r2["customAttributes"][0]["attributeId"] == "123"
    assert r2["customAttributes"][0]["attributeValue"] == "new_value"
    assert set(changes) == {
        "additional (None->info)",
        "custom attributes ({'attr': True} -> {'attr': 'new_value'})",
        "statusId (NOT_AVAILABLE->AVAILABLE)",
        "typeId (0->1)",
    }
