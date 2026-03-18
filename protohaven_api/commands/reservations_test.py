# pylint: skip-file
"""Test reservation commands"""
import datetime

import pytest

from protohaven_api.commands import reservations as r
from protohaven_api.testing import d, mkcli


@pytest.fixture(name="cli")
def fixture_cli(capsys):
    return mkcli(capsys, r)


def test_command_decorator():
    """Test the command decorator to make sure it passes args correctly"""

    @r.command(("--test", {"help": "test argument", "type": str, "default": "no"}))
    def fn(self, args):
        return args.test

    assert fn(None, ["--test=yes"]) == "yes"
    assert fn(None, []) == "no"


def test_sync_reservable_tools_empty(mocker, cli):
    """Behavior is OK when no data"""
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    r.airtable.get_areas.return_value = []
    r.airtable.get_tools.return_value = []
    r.booked.get_resource_group_map.return_value = {}
    r.booked.stage_custom_attributes.side_effect = lambda r, **c: r
    r.booked.get_resource.return_value = {}
    r.booked.get_resource_id_to_name_map.return_value = {}

    cli("sync_reservable_tools", ["--apply"])
    r.booked.update_resource.assert_not_called()
    r.booked.create_resource.assert_not_called()


def test_sync_reservable_tools_nodiffs(mocker, cli):
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    r.airtable.get_areas.return_value = [
        {"fields": {"Name": "Test Area", "Color": "#ffffff"}}
    ]
    mocker.patch.object(
        r.Commands, "_sync_reservable_tool", side_effect=lambda r, t: (r, [])
    )

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
    r.booked.get_resources.return_value = [
        {"resourceId": 1, "name": "Test Area - Test Tool"}
    ]

    cli("sync_reservable_tools", ["--apply"])

    r.booked.update_resource.assert_not_called()
    r.booked.create_resource.assert_not_called()


def test_sync_reservable_tools_diff(mocker, cli):
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    r.airtable.get_areas.return_value = [
        {"fields": {"Name": "Test Area", "Color": "#ffffff"}}
    ]
    mocker.patch.object(
        r.Commands,
        "_sync_reservable_tool",
        side_effect=lambda r, t: ({**r, "statusId": 3}, ["test change"]),
    )
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
    r.booked.get_resources.return_value = [
        {"resourceId": 1, "name": "Test Area - Test Tool"}
    ]
