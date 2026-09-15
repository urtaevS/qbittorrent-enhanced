from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([
        TorrentActionButton(entry.runtime_data, entry, "start", "Resume all"),
        TorrentActionButton(entry.runtime_data, entry, "stop", "Pause all"),
        TorrentActionButton(entry.runtime_data, entry, "recheck", "Recheck all"),
        TorrentActionButton(entry.runtime_data, entry, "reannounce", "Reannounce all"),
    ])


class TorrentActionButton(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator, entry, action, name):
        super().__init__(coordinator)
        self.action = action
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{action}_all"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="qBittorrent",
            manufacturer="qBittorrent",
        )

    async def async_press(self):
        hashes = [torrent["hash"] for torrent in self.coordinator.data["torrents"]]
        if not hashes:
            return
        await getattr(self.coordinator.api, self.action)(hashes)
        await self.coordinator.async_request_refresh()
