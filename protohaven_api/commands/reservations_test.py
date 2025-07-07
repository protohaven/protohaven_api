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
    r.booked.get_resource_id_to_name_map.return_value = {1: "Test Tool"}

    cli("sync_reservable_tools", ["--apply"])

    r.booked.create_resource.assert_not_called()
    r.booked.update_resource.assert_called_with(
        {
            "resourceId": 1,
            "name": "Test Area - Test Tool",
            "statusId": 3,
        }
    )


def test_reserve_equipment_for_class(mocker, cli):
    mocker.patch.object(
        r.airtable,
        "get_class_automation_schedule",
        return_value=[
            {
                "fields": {
                    "ID": 123,
                    "Name (from Area) (from Class)": ["a1"],
                    "Name (from Class)": "Test Class",
                    "Days (from Class)": [1],
                    "Hours (from Class)": [3],
                    "Start Time": d(0).isoformat(),
                },
            }
        ],
    )
    mocker.patch.object(
        r.airtable,
        "get_all_records",
        return_value=[
            {
                "fields": {
                    "Name (from Shop Area)": ["a1"],
                    "Tool Name": "t1",
                    "BookedResourceId": "1",
                }
            }
        ],
    )
    mocker.patch.object(r.booked, "reserve_resource")
    cli("reserve_equipment_for_class", ["--cls", "123", "--apply"])
    r.booked.reserve_resource.assert_called_with(
        "1", d(0), d(0) + datetime.timedelta(hours=3), title="Test Class"
    )


def test_reserve_equipment_from_template(mocker, cli):
    mocker.patch.object(
        r.airtable,
        "get_all_class_templates",
        return_value=[
            {
                "fields": {
                    "ID": 123,
                    "Name (from Area)": ["a1"],
                    "Name": "Test Class",
                    "Days": 1,
                    "Hours": 3,
                }
            }
        ],
    )
    mocker.patch.object(
        r.airtable,
        "get_all_records",
        return_value=[
            {
                "fields": {
                    "Name (from Shop Area)": ["a1"],
                    "Tool Name": "t1",
                    "BookedResourceId": "1",
                }
            }
        ],
    )
    mocker.patch.object(r.booked, "reserve_resource")
    cli(
        "reserve_equipment_from_template",
        ["--cls", "123", "--start", d(0).isoformat(), "--apply"],
    )
    r.booked.reserve_resource.assert_called_with(
        "1", d(0), d(0) + datetime.timedelta(hours=3), title="Test Class"
    )


def test_sync_booked_members_not_in_booked(mocker, cli):
    """Test sync_booked_members command function."""
    mocker.patch.object(
        r.neon,
        "search_all_members",
        return_value=[
            mocker.MagicMock(
                email="john@example.com",
                fname="John",
                lname="Doe",
                neon_id=12345,
                booked_id=None,
                can_reserve_tools=lambda: True,
            )
        ],
    )
    mocker.patch.object(r.booked, "get_all_users", return_value=[])
    mocker.patch.object(
        r.booked, "create_user_as_member", return_value={"userId": 456, "errors": []}
    )
    mocker.patch.object(r.neon, "set_booked_user_id")
    mocker.patch.object(r.booked, "update_user")
    mocker.patch.object(r.booked, "get_members_group", return_value={"users": []})
    mocker.patch.object(r.booked, "assign_members_group_users", return_value={})

    args = mocker.Mock()
    args.exclude = None
    args.apply = True

    got = cli("sync_booked_members", ["--apply"])
    assert len(got) == 1
    r.neon.set_booked_user_id.assert_called_with(12345, 456)
    r.booked.update_user.assert_not_called()
    r.booked.assign_members_group_users.assert_called_with({456})


def test_sync_booked_members_associate_existing(mocker, cli):
    """Test sync_booked_members command function with existing account"""
    mocker.patch.object(
        r.neon,
        "search_all_members",
        return_value=[
            mocker.MagicMock(
                email="john@example.com",
                fname="John",
                lname="Doe",
                neon_id=12345,
                booked_id=None,
                can_reserve_tools=lambda: True,
            )
        ],
    )
    mocker.patch.object(
        r.booked,
        "get_all_users",
        return_value=[
            {
                "id": 456,
                "firstName": "John",
                "lastName": "Doe",
                "emailAddress": "john@example.com",
            }
        ],
    )
    mocker.patch.object(r.booked, "create_user_as_member")
    mocker.patch.object(r.neon, "set_booked_user_id")
    mocker.patch.object(r.booked, "get_user")
    mocker.patch.object(r.booked, "update_user", return_value={})
    mocker.patch.object(r.booked, "get_members_group", return_value={"users": []})
    mocker.patch.object(r.booked, "assign_members_group_users", return_value={})

    args = mocker.Mock()
    args.exclude = None
    args.apply = True

    got = cli("sync_booked_members", ["--apply"])
    assert len(got) == 1
    r.neon.set_booked_user_id.assert_called_with(12345, 456)
    r.booked.create_user_as_member.assert_not_called()
    r.booked.assign_members_group_users.assert_called_with({456})


def test_sync_booked_members_update_associated(mocker, cli):
    """Test sync_booked_members command syncing with associated account"""

    # Note the addition of booked user ID
    mocker.patch.object(
        r.neon,
        "search_all_members",
        return_value=[
            mocker.MagicMock(
                email="john@example.com",
                fname="John",
                lname="Doe",
                neon_id=12345,
                booked_id=456,
                can_reserve_tools=lambda: True,
            )
        ],
    )

    # Note that no fields except the ID properly match the Neon values
    mocker.patch.object(
        r.booked,
        "get_all_users",
        return_value=[
            {"id": 456, "firstName": "A", "lastName": "B", "emailAddress": "c@d.com"}
        ],
    )
    mocker.patch.object(r.booked, "create_user_as_member")
    mocker.patch.object(r.neon, "set_booked_user_id")
    mocker.patch.object(
        r.booked,
        "get_user",
        return_value={
            "id": 456,
            "firstName": "A",
            "lastName": "B",
            "emailAddress": "c@d.com",
        },
    )
    mocker.patch.object(r.booked, "update_user", return_value={})
    mocker.patch.object(r.booked, "get_members_group", return_value={"users": []})
    mocker.patch.object(r.booked, "assign_members_group_users", return_value={})

    args = mocker.Mock()
    args.exclude = None
    args.apply = True

    got = cli("sync_booked_members", ["--apply"])
    assert len(got) == 1
    r.neon.set_booked_user_id.assert_not_called()
    r.booked.create_user_as_member.assert_not_called()
    r.neon.set_booked_user_id.assert_not_called()

    # Values are synced from Neon
    r.booked.update_user.assert_called_with(
        456,
        {
            "id": 456,
            "firstName": "John",
            "lastName": "Doe",
            "emailAddress": "john@example.com",
        },
    )
    r.booked.assign_members_group_users.assert_called_with({456})
