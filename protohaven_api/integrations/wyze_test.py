"""Test of methods in wyze integration"""

from protohaven_api.integrations import wyze as w


def test_get_door_states(mocker):
    """Test get_door_states for proper door state extraction"""
    m = mocker.Mock()
    m.product.type = w.ContactSensor.type
    m.nickname = "Front Door"
    m.mac = "00:11:22:33:44:55"
    m.is_online = True
    m.open_close_state = "open"

    mocker.patch.object(w, "cli", devices_list=lambda: [m])

    expected = [
        {
            "name": "Front Door",
            "mac": "00:11:22:33:44:55",
            "is_online": True,
            "open_close_state": "open",
        }
    ]

    result = list(w.get_door_states())
    assert result == expected


def test_get_camera_states(mocker):
    """Test get_camera_states function"""
    m = mocker.Mock()
    m.product.type = w.Camera.type
    m.nickname = "Camera 1"
    m.mac = "00:11:22:33:44:55"
    m.is_online = True

    mocker.patch.object(w, "cli", devices_list=lambda: [m])

    expected_result = [
        {"name": "Camera 1", "mac": "00:11:22:33:44:55", "is_online": True}
    ]
    result = list(w.get_camera_states())
    assert result == expected_result
