# pylint: skip-file
"""Test reservation commands"""
import pytest

from protohaven_api.commands import reservations as r


def test_command_decorator():
    """Test the command decorator to make sure it passes args correctly"""

    @r.command(("--test", {"help": "test argument", "type": str, "default": "no"}))
    def fn(self, args):
        return args.test

    assert fn(None, ["--test=yes"]) == "yes"
    assert fn(None, []) == "no"


def test_sync_reservable_tools_empty(mocker):
    """Behavior is OK when no data"""
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    r.airtable.get_areas.return_value = []
    r.airtable.get_tools.return_value = []
    r.booked.get_resource_group_map.return_value = {}
    r.booked.stage_custom_attributes.side_effect = lambda r, **c: r
    r.booked.get_resource.return_value = {}
    r.booked.get_resource_id_to_name_map.return_value = {}

    r.Commands().sync_reservable_tools([])
    r.booked.update_resource.assert_not_called()
    r.booked.create_resource.assert_not_called()


def test_sync_reservable_tools_nodiffs(mocker):
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    r.airtable.get_areas.return_value = [
        {"fields": {"Name": "Test Area", "Color": "#ffffff"}}
    ]
    r.airtable.get_tools.return_value = [
        {
            "id": "rec12345",
            "fields": {
                "Reservable": True,
                "Tool Name": "Test Tool",
                "Name (from Shop Area)": ["Test Area"],
                "BookedResourceId": 1,
            },
        }
    ]
    r.booked.get_resource_group_map.return_value = {"Test Area": 123}
    r.booked.stage_custom_attributes.side_effect = lambda r, **c: (r, {})
    r.booked.get_resource.return_value = {
        "name": "Test Area - Test Tool",
        "statusId": r.booked.STATUS_UNAVAILABLE,
        "typeId": r.booked.TYPE_TOOL,
        "color": "#ffffff",
        "allowMultiday": False,
    }
    r.booked.get_resource_id_to_name_map.return_value = {1: "Test Tool"}

    r.Commands().sync_reservable_tools(["--apply"])

    r.booked.update_resource.assert_not_called()
    r.booked.create_resource.assert_not_called()


def test_sync_reservable_tools_diff(mocker):
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    r.airtable.get_areas.return_value = [
        {"fields": {"Name": "Test Area", "Color": "#ffffff"}}
    ]
    r.airtable.get_tools.return_value = [
        {
            "id": "rec12345",
            "fields": {
                "Reservable": True,
                "Tool Name": "Test Tool",
                "Name (from Shop Area)": ["Test Area"],
                "BookedResourceId": 1,
            },
        }
    ]
    r.booked.get_resource_group_map.return_value = {"Test Area": 123}
    r.booked.stage_custom_attributes.side_effect = lambda r, **c: (r, {})
    r.booked.get_resource.return_value = {
        "name": "Incorrect",
        "statusId": r.booked.STATUS_AVAILABLE,
        "typeId": "whatever",
        "color": "wrong",
        "allowMultiday": False,
    }
    r.booked.get_resource_id_to_name_map.return_value = {1: "Test Tool"}

    r.Commands().sync_reservable_tools(["--apply"])

    r.booked.create_resource.assert_not_called()
    r.booked.update_resource.assert_called_with(
        {
            "name": "Test Area - Test Tool",
            "statusId": r.booked.STATUS_UNAVAILABLE,
            "typeId": r.booked.TYPE_TOOL,
            "color": "#ffffff",
            "allowMultiday": False,
        }
    )


def test_reserve_equipment_for_class(mocker):
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")

    r.Commands().reserve_equipment_for_class(["--cls=12345", "--apply"])
    raise NotImplementedError()


def test_reserve_equipment_from_template():
    raise NotImplementedError()
