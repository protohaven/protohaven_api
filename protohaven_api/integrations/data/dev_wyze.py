"""Mock implementation of Wyze integration using Nocodb"""

from dataclasses import dataclass

from protohaven_api.integrations import airtable_base


@dataclass
class Device:
    """Data for a Wyze device - not all fields may be needed for every type"""

    nickname: str
    mac: str
    is_online: bool
    open_close_state: bool


class DeviceSet:  # pylint: disable=too-few-public-methods
    """A set/list of devices, following Wyze API convention"""

    def __init__(self, ee):
        self.ee = ee

    def list(self):
        """Get devices as a list"""
        return self.ee


class Client:
    """Mock implementation of Wyze API client"""

    def __init__(self):
        pass

    def _all_devices(self, typ: str):
        ee = []
        for row in airtable_base.get_all_records("fake_wyze", "devices"):
            if row["fields"]["type"] == typ:
                ee.append(
                    Device(
                        nickname=row["fields"]["nickname"],
                        mac=row["fields"]["mac"],
                        is_online=row["fields"]["is_online"],
                        open_close_state=row["fields"].get("open_close_state"),
                    )
                )
        return DeviceSet(ee)

    @property
    def cameras(self):
        """Gets all cameras"""
        return self._all_devices("camera")

    @property
    def entry_sensors(self):
        """Gets all entry sensors"""
        return self._all_devices("entry_sensor")
