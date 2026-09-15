from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import QBittorrentApi, Torrent
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .exceptions import QBittorrentError

_LOGGER = logging.getLogger(__name__)


class QBittorrentCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Single polling source for qBittorrent state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: QBittorrentApi,
    ) -> None:
        self.api = api
        self.entry = entry
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(
                seconds=entry.data.get(
                    "update_interval", DEFAULT_UPDATE_INTERVAL
                )
            ),
        )

    async def async_setup(self) -> None:
        await self.api.discover()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            transfer = await self.api.transfer_info()
            torrents = await self.api.torrents_info()
            alternative_speed = await self.api.speed_limits_mode()
            speed_limits = await self.api.get_speed_limits()
            return {
                "transfer": transfer,
                "torrents": torrents,
                "alternative_speed": alternative_speed,
                "speed_limits": speed_limits,
                "info": self.api.info,
                "capabilities": self.api.capabilities,
            }
        except QBittorrentError as err:
            raise UpdateFailed(str(err)) from err

    def torrent(self, torrent_hash: str) -> Torrent | None:
        for torrent in self.data.get("torrents", []):
            if torrent.hash == torrent_hash:
                return torrent
        return None
