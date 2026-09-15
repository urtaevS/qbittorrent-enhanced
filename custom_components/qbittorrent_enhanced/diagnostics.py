from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.redact import async_redact_data

TO_REDACT = {
    "api_key",
    "password",
    "username",
    "Authorization",
    "authorization",
    "cookie",
    "cookies",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    info = coordinator.api.info
    data = {
        "config": dict(entry.data),
        "qBittorrent": {
            "version": info.version if info else None,
            "webapi_version": info.webapi_version if info else None,
            "build_info": info.build_info if info else {},
            "capabilities": (
                coordinator.api.capabilities.__dict__
                if info
                else {}
            ),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "torrent_count": len(coordinator.data.get("torrents", [])),
        },
    }
    return async_redact_data(data, TO_REDACT)
