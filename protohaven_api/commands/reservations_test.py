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


def test_area_colors(mocker):
    """_area_colors maps named Airtable areas to their colors"""
    c = r.Commands()
    c._area_colors.cache_clear()
    mocker.patch.object(r, "airtable")
    r.airtable.get_areas.return_value = [
        {"fields": {"Name": "Woodshop", "Color": "red"}},
        {"fields": {"Name": "Metal Shop"}},
        {"fields": {}},
    ]
    assert c._area_colors() == {"Woodshop": "red", "Metal Shop": None}


def test_sync_reservable_tool_missing_area(mocker):
    """Tools without an area cannot be synced"""
    c = r.Commands()
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    with pytest.raises(RuntimeError, match="missing name and/or area"):
        c._sync_reservable_tool({}, {"id": "t1", "fields": {"Tool Name": "Saw"}})


def test_sync_reservable_tool_success(mocker):
    """_sync_reservable_tool stages a Booked resource update"""
    c = r.Commands()
    c._area_colors.cache_clear()
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    r.airtable.get_areas.return_value = [
        {"fields": {"Name": "Woodshop", "Color": "red"}}
    ]
    r.booked.get_resource.return_value = {"resourceId": 5}
    stage = mocker.patch.object(
        r.booked, "stage_tool_update", return_value=("updated", ["change"])
    )

    got = c._sync_reservable_tool(
        {"resourceId": 5},
        {
            "id": "t1",
            "fields": {
                "Tool Name": "Saw",
                "Name (from Shop Area)": ["Woodshop"],
                "BookedResourceId": 5,
                "Clearance Code (from Clearance Required)": ["SBL"],
                "Tool Code": "SAW",
                "Current Status": "Green",
            },
        },
    )

    assert got == ("updated", ["change"])
    stage.assert_called_once_with(
        {"resourceId": 5},
        {"area": "Woodshop", "tool_code": "SAW", "clearance_code": "SBL"},
        reservable=True,
        name="Woodshop - Saw",
        color="red",
        allowMultiday=False,
    )


def test_sync_booked_permissions(mocker):
    """_sync_booked_permissions adds missing Member tool permissions only when apply"""
    c = r.Commands()
    mocker.patch.object(r, "booked")
    r.booked.get_members_group_tool_permissions.return_value = iter([1])
    all_resources = {
        1: {"resourceId": 1, "name": "A"},
        2: {"resourceId": 2, "name": "B"},
    }

    summary = []
    c._sync_booked_permissions({1, 2}, all_resources, summary, False)
    assert "Add to Members group: #2 B" in summary
    r.booked.set_members_group_tool_permissions.assert_not_called()

    c._sync_booked_permissions({1, 2}, all_resources, summary, True)
    r.booked.set_members_group_tool_permissions.assert_called_once_with({1, 2})


def test_sync_reservable_tools_mismatched_groups(mocker):
    """Airtable areas and Booked groups must match exactly"""
    c = r.Commands()
    c._area_colors.cache_clear()
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    r.airtable.get_areas.return_value = [{"fields": {"Name": "Woodshop"}}]
    r.booked.get_resource_group_map.return_value = {"Metal Shop": 1}

    with pytest.raises(RuntimeError, match="Mismatch in Airtable Areas"):
        c.sync_reservable_tools([], mocker.MagicMock())


def test_sync_reservable_tools_creates_placeholder_and_applies(mocker):
    """Missing Booked resources are created, back-propagated, updated, and summarized"""
    c = r.Commands()
    c._area_colors.cache_clear()
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "print_yaml")
    mocker.patch.object(
        r.Commands,
        "_sync_reservable_tool",
        return_value=({"resourceId": 9, "name": "Woodshop - Saw"}, ["change"]),
    )
    mocker.patch.object(r.Commands, "_sync_booked_permissions")

    r.airtable.get_areas.return_value = [
        {"fields": {"Name": "Woodshop", "Color": "red"}},
        {"fields": {"Name": "Metal Shop", "Color": "blue"}},
    ]
    r.booked.get_resource_group_map.return_value = {"Woodshop": 1, "Metal Shop": 2}
    r.booked.get_resources.return_value = []
    r.airtable.get_tools.return_value = [
        {
            "id": "t1",
            "fields": {
                "Reservable": True,
                "Tool Name": "Saw",
                "Name (from Shop Area)": ["Woodshop"],
                "BookedResourceId": 9,
                "Tool Code": "SAW",
            },
        }
    ]
    r.booked.create_resource.return_value = {"resourceId": 9}
    r.booked.get_resource_id_to_name_map.return_value = {9: "Woodshop - Saw"}

    c.sync_reservable_tools(
        ["--apply", "--filter=SAW", "--exclude_areas=Metal Shop"], mocker.MagicMock()
    )

    r.booked.create_resource.assert_called_once_with("placeholder")
    r.airtable.set_booked_resource_id.assert_called_once_with("t1", 9)
    r.booked.update_resource.assert_called_once_with(
        {"resourceId": 9, "name": "Woodshop - Saw"}
    )
    r.print_yaml.assert_called_once()


def test_sync_reservable_tools_extra_resources_raise(mocker):
    """Booked resources missing from Airtable are treated as errors"""
    c = r.Commands()
    c._area_colors.cache_clear()
    mocker.patch.object(r, "airtable")
    mocker.patch.object(r, "booked")
    mocker.patch.object(r.Commands, "_sync_booked_permissions")
    r.airtable.get_areas.return_value = [{"fields": {"Name": "Woodshop"}}]
    r.booked.get_resource_group_map.return_value = {"Woodshop": 1}
    r.booked.get_resources.return_value = []
    r.airtable.get_tools.return_value = []
    r.booked.get_resource_id_to_name_map.return_value = {1: "orphan"}

    with pytest.raises(RuntimeError, match="These resources exist in Booked"):
        c.sync_reservable_tools([], mocker.MagicMock())


def test_fetch_neon_sources(mocker):
    """Only members with email addresses and tool reservation rights are returned"""
    c = r.Commands()
    mocker.patch.object(r, "neon")
    m1 = mocker.MagicMock()
    m1.email = "a@x.com"
    m1.can_reserve_tools.return_value = True
    m2 = mocker.MagicMock()
    m2.email = None
    m2.can_reserve_tools.return_value = True
    m3 = mocker.MagicMock()
    m3.email = "b@x.com"
    m3.can_reserve_tools.return_value = False
    r.neon.search_all_members.return_value = [m1, m2, m3]
    assert c._fetch_neon_sources() == [m1]


def test_fetch_booked_sources(mocker):
    """Booked users are indexed by ID"""
    c = r.Commands()
    mocker.patch.object(r, "booked")
    u1 = mocker.MagicMock()
    u1.id = 1
    u2 = mocker.MagicMock()
    u2.id = 2
    r.booked.get_all_users.return_value = [u1, u2]
    assert c._fetch_booked_sources() == {1: u1, 2: u2}


def test_sync_booked_members_exclude(mocker):
    """Excluded members are skipped"""
    c = r.Commands()
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "neon")
    mocker.patch.object(r, "print_yaml")
    member = mocker.MagicMock()
    member.email = "a@x.com"
    c._fetch_neon_sources = mocker.MagicMock(return_value=[member])
    c._fetch_booked_sources = mocker.MagicMock(return_value={})
    r.booked.get_members_group.return_value = {"users": []}

    c.sync_booked_members(["--exclude=a@x.com"], mocker.MagicMock())
    r.neon.set_booked_user_id.assert_not_called()
    r.booked.assign_members_group_users.assert_not_called()


def test_sync_booked_members_include(mocker):
    """Members outside the explicit include list are skipped"""
    c = r.Commands()
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "neon")
    mocker.patch.object(r, "print_yaml")
    member = mocker.MagicMock()
    member.email = "a@x.com"
    c._fetch_neon_sources = mocker.MagicMock(return_value=[member])
    c._fetch_booked_sources = mocker.MagicMock(return_value={})
    r.booked.get_members_group.return_value = {"users": []}

    c.sync_booked_members(["--include=b@x.com"], mocker.MagicMock())
    r.neon.set_booked_user_id.assert_not_called()


def test_sync_booked_members_associate_existing_user(mocker):
    """An existing Booked user with the same email is associated with Neon"""
    c = r.Commands()
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "neon")
    mocker.patch.object(r, "print_yaml")

    member = mocker.MagicMock()
    member.email = "a@x.com"
    member.name = "A X"
    member.booked_id = None
    member.neon_id = "n1"
    member.fname = "A"
    member.lname = "X"
    user = mocker.MagicMock()
    user.id = 5
    user.email = "a@x.com"
    c._fetch_neon_sources = mocker.MagicMock(return_value=[member])
    c._fetch_booked_sources = mocker.MagicMock(return_value={5: user})
    r.booked.get_members_group.return_value = {"users": []}

    c.sync_booked_members(["--apply"], mocker.MagicMock())
    r.neon.set_booked_user_id.assert_called_once_with("n1", 5)
    r.booked.assign_members_group_users.assert_called_once_with([5])


def test_sync_booked_members_create_user_success(mocker):
    """Missing Booked users are created when apply is set"""
    c = r.Commands()
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "neon")
    mocker.patch.object(r, "print_yaml")

    member = mocker.MagicMock()
    member.email = "a@x.com"
    member.name = "A X"
    member.booked_id = None
    member.neon_id = "n1"
    member.fname = "A"
    member.lname = "X"
    c._fetch_neon_sources = mocker.MagicMock(return_value=[member])
    c._fetch_booked_sources = mocker.MagicMock(return_value={})
    r.booked.create_user_as_member.return_value = {"userId": 7}
    r.booked.get_members_group.return_value = {"users": []}

    c.sync_booked_members(["--apply"], mocker.MagicMock())
    r.booked.create_user_as_member.assert_called_once_with("A", "X", "a@x.com")
    r.neon.set_booked_user_id.assert_called_once_with("n1", 7)
    r.booked.assign_members_group_users.assert_called_once_with([7])


def test_sync_booked_members_create_user_errors(mocker):
    """Errors returned while creating a Booked user are summarized and skipped"""
    c = r.Commands()
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "neon")
    mocker.patch.object(r, "print_yaml")

    member = mocker.MagicMock()
    member.email = "a@x.com"
    member.name = "A X"
    member.booked_id = None
    member.neon_id = "n1"
    member.fname = "A"
    member.lname = "X"
    c._fetch_neon_sources = mocker.MagicMock(return_value=[member])
    c._fetch_booked_sources = mocker.MagicMock(return_value={})
    r.booked.create_user_as_member.return_value = {"errors": ["bad request"]}
    r.booked.get_members_group.return_value = {"users": []}

    c.sync_booked_members(["--apply"], mocker.MagicMock())
    r.neon.set_booked_user_id.assert_not_called()
    r.booked.assign_members_group_users.assert_not_called()


def test_sync_booked_members_invalid_booked_id(mocker):
    """A Neon member pointing to a missing Booked user raises"""
    c = r.Commands()
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "neon")
    member = mocker.MagicMock()
    member.email = "a@x.com"
    member.name = "A X"
    member.booked_id = 99
    member.neon_id = "n1"
    member.fname = "A"
    member.lname = "X"
    c._fetch_neon_sources = mocker.MagicMock(return_value=[member])
    c._fetch_booked_sources = mocker.MagicMock(return_value={})

    with pytest.raises(RuntimeError, match="invalid booked user ID"):
        c.sync_booked_members([], mocker.MagicMock())


def test_sync_booked_members_updates_mismatched_user(mocker):
    """Mismatched member data is corrected in Booked when apply is set"""
    c = r.Commands()
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "neon")
    mocker.patch.object(r, "print_yaml")

    member = mocker.MagicMock()
    member.email = "new@x.com"
    member.name = "New Name"
    member.booked_id = 1
    member.neon_id = "n1"
    member.fname = "New"
    member.lname = "Name"
    user = mocker.MagicMock()
    user.first_name = "Old"
    user.last_name = "Name"
    user.email = "old@x.com"
    c._fetch_neon_sources = mocker.MagicMock(return_value=[member])
    c._fetch_booked_sources = mocker.MagicMock(return_value={1: user})
    r.booked.get_user.return_value = {"id": 1}
    r.booked.get_members_group.return_value = {"users": []}

    c.sync_booked_members(["--apply"], mocker.MagicMock())
    r.booked.update_user.assert_called_once()
    data = r.booked.update_user.call_args.args[1]
    assert data["firstName"] == "New"
    assert data["lastName"] == "Name"
    assert data["emailAddress"] == "new@x.com"
    r.booked.assign_members_group_users.assert_called_once_with([1])


def test_cleanup_orphaned_class_reservations_no_classes(mocker):
    """Cleanup refuses to run when no published classes were found"""
    c = r.Commands()
    mocker.patch.object(r, "eauto")
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "tznow", return_value=d(0))
    r.eauto.fetch_upcoming_events.return_value = []
    r.booked.get_automation_reservations.return_value = []

    with pytest.raises(RuntimeError, match="No classes found"):
        c.cleanup_orphaned_class_reservations([], mocker.MagicMock())


def test_cleanup_orphaned_class_reservations(mocker):
    """Orphaned reservations are identified and deleted only when apply is set"""
    c = r.Commands()
    mocker.patch.object(r, "eauto")
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "print_yaml")
    mocker.patch.object(r, "tznow", return_value=d(0, 10))

    event = mocker.MagicMock()
    event.airtable_data = True
    event.event_id = "e1"
    event.name = "Class"
    event.start_date = d(1, 9)
    event.end_date = d(1, 12)
    event.areas = ["Woodshop"]
    event.sessions = [(d(1, 10), d(1, 12))]
    r.eauto.fetch_upcoming_events.return_value = [event]
    r.booked.get_resource_area_map.return_value = {"Woodshop": [5]}
    r.booked.get_automation_reservations.return_value = [
        {
            "resourceId": 5,
            "referenceNumber": "R1",
            "resourceName": "Woodshop - Saw",
            "startDate": d(1, 10),
            "title": "Class",
        },
        {
            "resourceId": 5,
            "referenceNumber": "R2",
            "resourceName": "Woodshop - Saw",
            "startDate": d(1, 13),
            "title": "Orphan",
        },
        {
            "resourceId": 6,
            "referenceNumber": "R3",
            "resourceName": "Unknown - X",
            "startDate": d(1, 10),
            "title": "No area",
        },
    ]

    c.cleanup_orphaned_class_reservations([], mocker.MagicMock())
    r.booked.delete_reservation.assert_not_called()
    assert r.print_yaml.call_count == 1

    c.cleanup_orphaned_class_reservations(["--apply"], mocker.MagicMock())
    r.booked.delete_reservation.assert_called_once_with("R2")


def test_cleanup_orphaned_class_reservations_max_and_delete_error(mocker):
    """Cleanup stops at max and records delete failures"""
    c = r.Commands()
    mocker.patch.object(r, "eauto")
    mocker.patch.object(r, "booked")
    mocker.patch.object(r, "print_yaml")
    mocker.patch.object(r, "tznow", return_value=d(0, 10))

    event = mocker.MagicMock()
    event.airtable_data = True
    event.event_id = "e1"
    event.name = "Class"
    event.start_date = d(1, 9)
    event.end_date = d(1, 12)
    event.areas = ["Woodshop"]
    event.sessions = [(d(1, 10), d(1, 12))]
    r.eauto.fetch_upcoming_events.return_value = [event]
    r.booked.get_resource_area_map.return_value = {"Woodshop": [5]}
    r.booked.get_automation_reservations.return_value = [
        {
            "resourceId": 5,
            "referenceNumber": "R2",
            "resourceName": "Woodshop - Saw",
            "startDate": d(1, 13),
            "title": "Orphan 1",
        },
        {
            "resourceId": 5,
            "referenceNumber": "R4",
            "resourceName": "Woodshop - Saw",
            "startDate": d(1, 14),
            "title": "Orphan 2",
        },
    ]
    r.booked.delete_reservation.side_effect = RuntimeError("boom")

    args = mocker.MagicMock()
    args.apply = True
    args.days = 90
    args.max = 1
    c.cleanup_orphaned_class_reservations.__wrapped__(c, args, mocker.MagicMock())
    r.booked.delete_reservation.assert_called_once_with("R2")
    r.print_yaml.assert_called_once()
