from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CONNECTION_SPEED_MBPS, DOMAIN

MB = 1_000_000


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([
        SpeedLimitNumber(entry.runtime_data, entry, "dl_limit"),
        SpeedLimitNumber(entry.runtime_data, entry, "up_limit"),
        SpeedLimitNumber(entry.runtime_data, entry, "alt_dl_limit"),
        SpeedLimitNumber(entry.runtime_data, entry, "alt_up_limit"),
    ])


class SpeedLimitNumber(CoordinatorEntity, NumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 1000
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "MB/s"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator)
        self.config_entry = entry
        self.key = key
        self._attr_name = {
            "dl_limit": "Global download limit",
            "up_limit": "Global upload limit",
            "alt_dl_limit": "Alternative download limit",
            "alt_up_limit": "Alternative upload limit",
        }[key]
        # qBittorrent stores values in bytes/s; HA exposes MB/s.
        # If connection speed is configured, cap the sliders to the physical
        # connection speed. Without it, keep the safe legacy maxima.
        connection_mbps = entry.options.get(CONF_CONNECTION_SPEED_MBPS)
        connection_mb_s = (float(connection_mbps) / 8.0) if connection_mbps else None
        configured_max = 10.0 if key.startswith("alt_") else 150.0
        if connection_mb_s is not None:
            configured_max = min(configured_max, connection_mb_s)
        self._attr_native_max_value = round(configured_max, 1)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="qBittorrent",
            manufacturer="qBittorrent",
        )
        self._optimistic_value: float | None = None

    @property
    def native_value(self):
        if self._optimistic_value is not None:
            return self._optimistic_value
        return self._bytes_to_mb(self.coordinator.data["speed_limits"].get(self.key, 0))

    @staticmethod
    def _bytes_to_mb(value: int | float) -> float:
        return round(float(value) / MB, 3)

    async def async_set_native_value(self, value):
        connection_mbps = self.config_entry.options.get(CONF_CONNECTION_SPEED_MBPS)
        connection_mb_s = (float(connection_mbps) / 8.0) if connection_mbps else None
        maximum = 10.0 if self.key.startswith("alt_") else 150.0
        if connection_mb_s is not None:
            maximum = min(maximum, connection_mb_s)
        value = max(0.0, min(maximum, float(value)))
        self._optimistic_value = value
        limits = dict(self.coordinator.data["speed_limits"])
        limits[self.key] = int(round(value * MB))
        # Update immediately so both the entity row and settings screen show
        # the selected value without waiting for the next coordinator poll.
        self.coordinator.data["speed_limits"] = limits
        self.async_write_ha_state()
        try:
            await self.coordinator.api.set_speed_limits(**limits)
            await self.coordinator.async_request_refresh()
        finally:
            self._optimistic_value = None
            self.async_write_ha_state()
