from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([AlternativeSpeedSwitch(entry.runtime_data, entry)])


class AlternativeSpeedSwitch(
    CoordinatorEntity, SwitchEntity
):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "Alternative speed"
        self._attr_unique_id = f"{entry.entry_id}_alternative_speed"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="qBittorrent",
            manufacturer="qBittorrent",
        )

    @property
    def is_on(self):
        return bool(self.coordinator.data["alternative_speed"])

    async def async_turn_on(self, **kwargs):
        if not self.is_on:
            await self.coordinator.api.toggle_speed_limits_mode()
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        if self.is_on:
            await self.coordinator.api.toggle_speed_limits_mode()
            await self.coordinator.async_request_refresh()
