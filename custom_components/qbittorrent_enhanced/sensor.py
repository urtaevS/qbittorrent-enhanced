from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfDataRate, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities([
        SpeedSensor(coordinator, entry, "download"),
        SpeedSensor(coordinator, entry, "upload"),
        SessionDataSensor(coordinator, entry, "download"),
        SessionDataSensor(coordinator, entry, "upload"),
        TorrentCountSensor(coordinator, entry, "all"),
        TorrentCountSensor(coordinator, entry, "downloading"),
        TorrentCountSensor(coordinator, entry, "seeding"),
        TorrentCountSensor(coordinator, entry, "paused"),
        TorrentCountSensor(coordinator, entry, "errored"),
        ConnectionStatusSensor(coordinator, entry),
        DhtNodesSensor(coordinator, entry),
    ])


class BaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="qBittorrent",
            manufacturer="qBittorrent",
        )


class SpeedSensor(BaseSensor):
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND

    def __init__(self, coordinator, entry, direction):
        super().__init__(coordinator, entry)
        self.direction = direction
        self._attr_name = f"{direction.title()} speed"
        self._attr_unique_id = f"{entry.entry_id}_{direction}_speed"

    @property
    def native_value(self):
        key = "dl_info_speed" if self.direction == "download" else "up_info_speed"
        return self.coordinator.data.get("transfer", {}).get(key, 0)


class SessionDataSensor(BaseSensor):
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES

    def __init__(self, coordinator, entry, direction):
        super().__init__(coordinator, entry)
        self.direction = direction
        self._attr_name = f"Session {direction}ed"
        self._attr_unique_id = f"{entry.entry_id}_session_{direction}"

    @property
    def native_value(self):
        key = "dl_info_data" if self.direction == "download" else "up_info_data"
        return self.coordinator.data.get("transfer", {}).get(key, 0)


class TorrentCountSensor(BaseSensor):
    def __init__(self, coordinator, entry, kind):
        super().__init__(coordinator, entry)
        self.kind = kind
        self._attr_name = f"{kind.title()} torrents"
        self._attr_unique_id = f"{entry.entry_id}_torrents_{kind}"
        self._attr_native_unit_of_measurement = "torrents"

    @property
    def native_value(self):
        torrents = self.coordinator.data.get("torrents", [])
        if self.kind == "all":
            return len(torrents)
        if self.kind == "downloading":
            return sum(t.state in {"downloading", "metaDL"} for t in torrents)
        if self.kind == "seeding":
            return sum(t.state in {"uploading", "stalledUP"} for t in torrents)
        if self.kind == "paused":
            return sum(t.state in {"pausedDL", "pausedUP"} for t in torrents)
        if self.kind == "errored":
            return sum(t.state in {"error", "missingFiles"} for t in torrents)
        return 0


class ConnectionStatusSensor(BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "Connection status"
        self._attr_unique_id = f"{entry.entry_id}_connection_status"

    @property
    def native_value(self):
        return self.coordinator.data.get("transfer", {}).get(
            "connection_status", "unknown"
        )


class DhtNodesSensor(BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "DHT nodes"
        self._attr_unique_id = f"{entry.entry_id}_dht_nodes"

    @property
    def native_value(self):
        return self.coordinator.data.get("transfer", {}).get("dht_nodes", 0)
