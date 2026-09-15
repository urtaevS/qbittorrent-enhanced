from __future__ import annotations

import aiohttp
from dataclasses import asdict
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, HomeAssistantError, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .api import QBittorrentApi
from .exceptions import QBittorrentDuplicateError
from .const import (
    AUTH_API_KEY, CONF_API_KEY, CONF_AUTH_METHOD, CONF_PASSWORD, CONF_USERNAME,
    CONF_VERIFY_SSL, DOMAIN, SERVICE_CATEGORY, SERVICE_DELETE,
    SERVICE_DELETE_FILES, SERVICE_HASH, SERVICE_HASHES, SERVICE_REANNOUNCE,
    SERVICE_RECHECK, SERVICE_SET_CATEGORY, SERVICE_START, SERVICE_STOP, SERVICE_ADD_MAGNET,
)
from .coordinator import QBittorrentCoordinator

PLATFORMS = ["sensor", "switch", "number", "button"]
SERVICE_GET_TORRENTS = "get_torrents"
SERVICE_DOMAIN_ALIAS = "qbittorrent_enh"


def _validate_magnet(value):
    value = value.strip()
    if not value.lower().startswith("magnet:?"):
        raise vol.Invalid("A magnet link is required")
    return value


def _mbps_to_bytes(value):
    if value is None:
        return None
    return int(round(float(value) * 1_000_000))


def _hashes_from_call(call):
    hashes = call.data.get(SERVICE_HASHES)
    if hashes:
        return hashes
    torrent_hash = call.data.get(SERVICE_HASH)
    if torrent_hash:
        return [torrent_hash]
    raise vol.Invalid("A torrent hash or hashes is required")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    async def get_api(call):
        entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        if entry is None or entry.domain != DOMAIN or entry.runtime_data is None:
            raise vol.Invalid("Unknown qBittorrent entry")
        return entry.runtime_data.api

    async def get_torrents(call: ServiceCall) -> dict[str, object]:
        """Return the coordinator-owned normalized torrent collection.

        This is the frontend/card data channel: the card talks to Home Assistant
        and never opens a direct qBittorrent connection.
        """
        entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        if entry is None or entry.domain != DOMAIN or entry.runtime_data is None:
            raise vol.Invalid("Unknown qBittorrent entry")
        coordinator = entry.runtime_data
        torrents = coordinator.data.get("torrents", [])
        return {
            "entry_id": entry.entry_id,
            "server": {
                "version": coordinator.data.get("info").version
                if coordinator.data.get("info")
                else None,
                "webapi_version": coordinator.data.get("info").webapi_version
                if coordinator.data.get("info")
                else None,
            },
            "torrents": [
                {**asdict(torrent), "tags": list(torrent.tags)}
                for torrent in torrents
            ],
        }

    async def handler(call):
        api = await get_api(call)
        service = call.service
        if service == SERVICE_ADD_MAGNET:
            magnet_url = call.data["magnet_url"]
            try:
                result = await api.add_magnet(
                    magnet_url=magnet_url,
                    save_path=call.data.get("save_path"),
                    category=call.data.get("category"),
                    tags=call.data.get("tags"),
                    skip_checking=call.data.get("skip_checking"),
                    paused=call.data.get("paused"),
                    content_layout=call.data.get("content_layout"),
                    rename=call.data.get("rename"),
                    upload_limit=_mbps_to_bytes(call.data.get("upload_limit")),
                    download_limit=_mbps_to_bytes(call.data.get("download_limit")),
                    ratio_limit=call.data.get("ratio_limit"),
                    seeding_time_limit=call.data.get("seeding_time_limit"),
                    auto_tmm=call.data.get("auto_tmm"),
                )
                entry = hass.config_entries.async_get_entry(call.data["entry_id"])
                if entry and entry.runtime_data:
                    await entry.runtime_data.async_request_refresh()
                return result if call.return_response else None
            except QBittorrentDuplicateError:
                torrent_hash = api.magnet_info_hash(magnet_url)
                if torrent_hash:
                    existing = await api.find_torrent_by_hash(torrent_hash)
                    if existing:
                        result = {
                            "status": "already_exists",
                            "hash": existing.hash,
                            "name": existing.name,
                            "state": existing.state,
                        }
                        return result if call.return_response else None
                raise HomeAssistantError("Torrent already exists in qBittorrent")
        hashes = _hashes_from_call(call)
        if service == SERVICE_START:
            await api.start(hashes)
        elif service == SERVICE_STOP:
            await api.stop(hashes)
        elif service == SERVICE_RECHECK:
            await api.recheck(hashes)
        elif service == SERVICE_REANNOUNCE:
            await api.reannounce(hashes)
        elif service == SERVICE_DELETE:
            await api.delete(hashes, call.data.get(SERVICE_DELETE_FILES, False))
        elif service == SERVICE_SET_CATEGORY:
            await api.set_category(hashes, call.data["category"])
        elif service == "set_tags":
            await api.set_tags(hashes, call.data["tags"])
        elif service == "remove_tags":
            await api.remove_tags(hashes, call.data["tags"])
        elif service == "set_download_limit":
            await api.set_download_limit(hashes, _mbps_to_bytes(call.data["limit"]))
        elif service == "set_upload_limit":
            await api.set_upload_limit(hashes, _mbps_to_bytes(call.data["limit"]))
        elif service == "set_priority":
            await api.set_priority(hashes, call.data["priority"])
        elif service == "set_force_start":
            await api.set_force_start(hashes, call.data["value"])
        elif service == "set_location":
            await api.set_location(hashes, call.data["location"])
        elif service == "rename_torrent":
            await api.rename(call.data["hash"], call.data["name"])
        entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        if entry and entry.runtime_data:
            await entry.runtime_data.async_request_refresh()

    hash_schema = {
        vol.Required("entry_id"): cv.string,
        vol.Optional("hash"): cv.string,
        vol.Optional("hashes"): vol.All(cv.ensure_list, [cv.string]),
    }

    service_schemas = {
        SERVICE_ADD_MAGNET: {
            vol.Required("entry_id"): cv.string,
            vol.Required("magnet_url"): vol.All(cv.string, _validate_magnet),
            vol.Optional("save_path"): cv.string,
            vol.Optional("category"): cv.string,
            vol.Optional("tags"): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional("skip_checking", default=False): bool,
            vol.Optional("paused", default=False): bool,
            vol.Optional("content_layout"): vol.In(["Original", "Subfolder", "NoSubfolder"]),
            vol.Optional("rename"): cv.string,
            vol.Optional("upload_limit"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1000)),
            vol.Optional("download_limit"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1000)),
            vol.Optional("ratio_limit"): vol.All(vol.Coerce(float), vol.Range(min=-1)),
            vol.Optional("seeding_time_limit"): vol.All(vol.Coerce(int), vol.Range(min=-1)),
            vol.Optional("auto_tmm"): bool,
        },
        SERVICE_START: hash_schema,
        SERVICE_STOP: hash_schema,
        SERVICE_RECHECK: hash_schema,
        SERVICE_REANNOUNCE: hash_schema,
        SERVICE_DELETE: {**hash_schema, vol.Optional(SERVICE_DELETE_FILES, default=False): bool},
        SERVICE_SET_CATEGORY: {**hash_schema, vol.Required("category"): cv.string},
        "set_tags": {**hash_schema, vol.Required("tags"): vol.All(cv.ensure_list, [cv.string])},
        "remove_tags": {**hash_schema, vol.Required("tags"): vol.All(cv.ensure_list, [cv.string])},
        "set_download_limit": {**hash_schema, vol.Required("limit"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1000))},
        "set_upload_limit": {**hash_schema, vol.Required("limit"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1000))},
        "set_priority": {**hash_schema, vol.Required("priority"): vol.In(["increase", "decrease", "top", "bottom"])},
        "set_force_start": {**hash_schema, vol.Required("value"): bool},
        "set_location": {**hash_schema, vol.Required("location"): cv.string},
        "rename_torrent": {
            vol.Required("entry_id"): cv.string,
            vol.Required("hash"): cv.string,
            vol.Required("name"): cv.string,
        },
    }

    for name, schema in service_schemas.items():
        if name == SERVICE_ADD_MAGNET:
            hass.services.async_register(
                DOMAIN,
                name,
                handler,
                schema=vol.Schema(schema),
                supports_response=SupportsResponse.OPTIONAL,
            )
        else:
            hass.services.async_register(
                DOMAIN, name, handler, schema=vol.Schema(schema)
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TORRENTS,
        get_torrents,
        schema=vol.Schema({vol.Required("entry_id"): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=True)
    )
    if entry.data[CONF_AUTH_METHOD] == AUTH_API_KEY:
        kwargs = {"api_key": entry.data[CONF_API_KEY]}
    else:
        kwargs = {
            "username": entry.data[CONF_USERNAME],
            "password": entry.data[CONF_PASSWORD],
        }

    api = QBittorrentApi(
        session, entry.data["host"], entry.data[CONF_VERIFY_SSL], **kwargs
    )
    api._session_owner = session  # noqa: SLF001
    coordinator = QBittorrentCoordinator(hass, entry, api)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.runtime_data:
        api = entry.runtime_data.api
        session = getattr(api, "_session_owner", None)
        if session is not None:
            await session.close()
    return unload_ok
