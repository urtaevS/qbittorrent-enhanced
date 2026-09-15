from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse
import base64
import json
import re

import aiohttp

from .const import API_BASE
from .exceptions import (
    QBittorrentApiError,
    QBittorrentAuthError,
    QBittorrentConnectionError,
    QBittorrentDuplicateError,
)


@dataclass(frozen=True)
class QBittorrentInfo:
    version: str
    webapi_version: str
    build_info: dict[str, Any]


@dataclass(frozen=True)
class QBittorrentCapabilities:
    speed_limits_v2: bool
    api_key_auth: bool
    torrent_tags: bool
    torrent_location: bool
    torrent_rename: bool


@dataclass(frozen=True)
class Torrent:
    """Stable normalized representation shared by HA and the future card."""

    hash: str
    name: str
    state: str
    progress: float
    size: int
    total_size: int
    amount_left: int
    downloaded: int
    uploaded: int
    download_speed: int
    upload_speed: int
    download_speed_avg: int
    upload_speed_avg: int
    eta: int
    ratio: float
    category: str
    tags: tuple[str, ...]
    save_path: str
    added_on: int
    completion_on: int
    seeding_time: int
    num_seeds: int
    num_leechs: int
    num_complete: int
    num_incomplete: int
    availability: float
    priority: int
    auto_tmm: bool
    super_seeding: bool
    sequential_download: bool
    first_last_piece_prio: bool

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Torrent":
        tags = data.get("tags", "")
        if isinstance(tags, str):
            normalized_tags = tuple(
                sorted(t.strip() for t in tags.split(",") if t.strip())
            )
        else:
            normalized_tags = tuple(sorted(str(t) for t in tags))

        return cls(
            hash=str(data.get("hash", "")),
            name=str(data.get("name", "")),
            state=str(data.get("state", "unknown")),
            progress=float(data.get("progress", 0.0)),
            size=int(data.get("size", 0)),
            total_size=int(data.get("total_size", data.get("size", 0))),
            amount_left=int(data.get("amount_left", 0)),
            downloaded=int(data.get("downloaded", 0)),
            uploaded=int(data.get("uploaded", 0)),
            download_speed=int(data.get("dlspeed", data.get("download_speed", 0))),
            upload_speed=int(data.get("upspeed", data.get("upload_speed", 0))),
            download_speed_avg=int(data.get("dl_speed_avg", data.get("download_speed_avg", 0))),
            upload_speed_avg=int(data.get("up_speed_avg", data.get("upload_speed_avg", 0))),
            eta=int(data.get("eta", 0)),
            ratio=float(data.get("ratio", 0.0)),
            category=str(data.get("category", "")),
            tags=normalized_tags,
            save_path=str(data.get("save_path", "")),
            added_on=int(data.get("added_on", 0)),
            completion_on=int(data.get("completion_on", 0)),
            seeding_time=int(data.get("seeding_time", 0)),
            num_seeds=int(data.get("num_seeds", 0)),
            num_leechs=int(data.get("num_leechs", 0)),
            num_complete=int(data.get("num_complete", 0)),
            num_incomplete=int(data.get("num_incomplete", 0)),
            availability=float(data.get("availability", 0.0)),
            priority=int(data.get("priority", 0)),
            auto_tmm=bool(data.get("auto_tmm", False)),
            super_seeding=bool(data.get("super_seeding", False)),
            sequential_download=bool(
                data.get("seq_dl", data.get("sequential_download", False))
            ),
            first_last_piece_prio=bool(
                data.get(
                    "f_l_piece_prio",
                    data.get("first_last_piece_prio", False),
                )
            ),
        )


class QBittorrentApi:
    """Async qBittorrent WebAPI v2 client.

    Authentication and endpoint details are isolated here so HA entities,
    services and the frontend contract remain independent of qBittorrent's
    authentication implementation.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        verify_ssl: bool,
        *,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._verify_ssl = verify_ssl
        self._api_key = api_key
        self._username = username
        self._password = password
        self._logged_in = False
        self.info: QBittorrentInfo | None = None

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def capabilities(self) -> QBittorrentCapabilities:
        version = self.info.webapi_version if self.info else ""
        try:
            parts = tuple(int(part) for part in version.split("."))
        except ValueError:
            parts = ()

        return QBittorrentCapabilities(
            speed_limits_v2=parts >= (2, 16, 0),
            api_key_auth=parts >= (2, 14, 1),
            torrent_tags=parts >= (2, 0, 0),
            torrent_location=parts >= (2, 0, 0),
            torrent_rename=parts >= (2, 0, 0),
        )

    def _url(self, path: str) -> str:
        return f"{self._base_url}{API_BASE}{path}"

    def _headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {"Referer": f"{self._base_url}/"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: Any = None,
        retry_auth: bool = True,
    ) -> Any:
        if not self._api_key and not self._logged_in:
            await self.login()

        try:
            async with self._session.request(
                method,
                self._url(path),
                headers=self._headers(),
                params=params,
                data=data,
                ssl=self._verify_ssl,
            ) as response:
                if response.status in (401, 403):
                    if retry_auth and not self._api_key and response.status == 403:
                        self._logged_in = False
                        await self.login()
                        return await self._request(
                            method,
                            path,
                            params=params,
                            data=data,
                            retry_auth=False,
                        )
                    raise QBittorrentAuthError(
                        f"qBittorrent returned HTTP {response.status}"
                    )

                if response.status == 409:
                    body = await response.text()
                    raise QBittorrentDuplicateError(
                        body[:300] or "Torrent already exists"
                    )

                if response.status >= 400:
                    body = await response.text()
                    raise QBittorrentApiError(
                        f"qBittorrent returned HTTP {response.status}: {body[:300]}"
                    )

                if response.status == 204:
                    return None

                text = await response.text()
                if not text:
                    return None

                if "json" in response.headers.get("Content-Type", ""):
                    return await response.json(content_type=None)
                return text

        except (QBittorrentAuthError, QBittorrentApiError):
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise QBittorrentConnectionError(str(err)) from err

    async def login(self) -> None:
        if self._api_key:
            return

        if self._username is None or self._password is None:
            raise QBittorrentAuthError("Username/password are not configured")

        try:
            async with self._session.post(
                self._url("/auth/login"),
                headers={
                    "Referer": f"{self._base_url}/",
                    "Origin": self._base_url,
                },
                data={
                    "username": self._username,
                    "password": self._password,
                },
                ssl=self._verify_ssl,
            ) as response:
                body = await response.text()

                if response.status == 401:
                    raise QBittorrentAuthError("Invalid qBittorrent credentials")

                if response.status >= 400:
                    raise QBittorrentApiError(
                        f"Login failed with HTTP {response.status}: {body[:300]}"
                    )

                if response.status == 204:
                    self._logged_in = True
                    return

                if body.strip().lower() != "ok.":
                    raise QBittorrentAuthError("qBittorrent login was rejected")

                self._logged_in = True

        except (QBittorrentAuthError, QBittorrentApiError):
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise QBittorrentConnectionError(str(err)) from err

    async def discover(self) -> QBittorrentInfo:
        self.info = QBittorrentInfo(
            version=str(await self._request("GET", "/app/version")),
            webapi_version=str(await self._request("GET", "/app/webapiVersion")),
            build_info=await self._request("GET", "/app/buildInfo") or {},
        )
        return self.info

    async def transfer_info(self) -> dict[str, Any]:
        return await self._request("GET", "/transfer/info")

    async def speed_limits_mode(self) -> bool:
        value = await self._request("GET", "/transfer/speedLimitsMode")
        return str(value).lower() in ("1", "true")

    async def toggle_speed_limits_mode(self) -> None:
        await self._request("POST", "/transfer/toggleSpeedLimitsMode")

    async def get_speed_limits(self) -> dict[str, int]:
        if self.capabilities.speed_limits_v2:
            result = await self._request("GET", "/transfer/getSpeedLimits")
            return {key: int(value) for key, value in result.items()}

        # qBittorrent WebAPI < 2.16 exposes alternative limits through
        # app/preferences (KiB/s), while global limits are exposed through
        # transfer endpoints (bytes/s).
        transfer = await self.transfer_info()
        preferences = await self._request("GET", "/app/preferences")
        return {
            "up_limit": int(transfer.get("up_rate_limit", 0)),
            "dl_limit": int(transfer.get("dl_rate_limit", 0)),
            "alt_up_limit": int(preferences.get("alt_up_limit", 0)) * 1024,
            "alt_dl_limit": int(preferences.get("alt_dl_limit", 0)) * 1024,
        }

    async def set_speed_limits(self, **limits: int) -> None:
        if self.capabilities.speed_limits_v2:
            await self._request(
                "POST", "/transfer/setSpeedLimits", data=limits
            )
            return

        # Keep the old API path fully functional, including alternative
        # limits, which are stored by qBittorrent as KiB/s preferences.
        await self._request(
            "POST",
            "/transfer/setUploadLimit",
            data={"limit": limits["up_limit"]},
        )
        await self._request(
            "POST",
            "/transfer/setDownloadLimit",
            data={"limit": limits["dl_limit"]},
        )
        await self._request(
            "POST",
            "/app/setPreferences",
            data={"json": json.dumps({
                "alt_up_limit": max(0, int(limits["alt_up_limit"]) // 1024),
                "alt_dl_limit": max(0, int(limits["alt_dl_limit"]) // 1024),
            })},
        )

    async def torrents_info(self, **filters: Any) -> list[Torrent]:
        params = {key: value for key, value in filters.items() if value is not None}
        raw = await self._request("GET", "/torrents/info", params=params)
        return [Torrent.from_api(item) for item in raw]

    @staticmethod
    def magnet_info_hash(magnet_url: str) -> str | None:
        """Extract a v1 BitTorrent info hash from a magnet URI."""
        try:
            values = parse_qs(urlparse(magnet_url).query).get("xt", [])
        except ValueError:
            return None
        for value in values:
            if not value.lower().startswith("urn:btih:"):
                continue
            raw = value[9:]
            if re.fullmatch(r"[0-9a-fA-F]{40}", raw):
                return raw.lower()
            if re.fullmatch(r"[A-Za-z2-7]{32}", raw):
                try:
                    return base64.b32decode(raw.upper()).hex()
                except Exception:
                    return None
        return None

    async def find_torrent_by_hash(self, torrent_hash: str) -> Torrent | None:
        """Find an existing torrent by its info hash."""
        torrents = await self.torrents_info(hash=torrent_hash)
        return torrents[0] if torrents else None

    async def add_magnet(
        self,
        *,
        magnet_url: str,
        save_path: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        skip_checking: bool | None = None,
        paused: bool | None = None,
        content_layout: str | None = None,
        rename: str | None = None,
        upload_limit: int | None = None,
        download_limit: int | None = None,
        ratio_limit: float | None = None,
        seeding_time_limit: int | None = None,
        auto_tmm: bool | None = None,
    ) -> dict[str, Any]:
        """Add a torrent from a single magnet link."""
        magnet_url = magnet_url.strip()
        if not magnet_url.lower().startswith("magnet:?"):
            raise ValueError("A magnet link is required")
        if content_layout is not None and content_layout not in {
            "Original", "Subfolder", "NoSubfolder"
        }:
            raise ValueError("Unsupported content_layout")

        fields: dict[str, Any] = {"urls": magnet_url}
        if save_path is not None:
            fields["savepath"] = save_path
        if category is not None:
            fields["category"] = category
        if tags:
            fields["tags"] = ",".join(tags)
        if skip_checking is not None and not self._webapi_at_least(2, 16, 0):
            fields["skip_checking"] = str(skip_checking).lower()
        if paused is not None:
            fields["paused"] = str(paused).lower()
        if content_layout is not None:
            fields["contentLayout"] = content_layout
        if rename is not None:
            fields["rename"] = rename
        if upload_limit is not None:
            fields["upLimit"] = int(upload_limit)
        if download_limit is not None:
            fields["dlLimit"] = int(download_limit)
        if ratio_limit is not None:
            fields["ratioLimit"] = float(ratio_limit)
        if seeding_time_limit is not None:
            fields["seedingTimeLimit"] = int(seeding_time_limit)
        if auto_tmm is not None:
            fields["autoTMM"] = str(auto_tmm).lower()

        result = await self._request("POST", "/torrents/add", data=fields)
        if isinstance(result, dict):
            return result
        return {"message": result}

    def _webapi_at_least(self, major: int, minor: int, patch: int = 0) -> bool:
        version = self.info.webapi_version if self.info else ""
        try:
            parts = tuple(int(part) for part in version.split(".")[:3])
        except ValueError:
            return False
        parts = parts + (0,) * (3 - len(parts))
        return parts >= (major, minor, patch)

    async def _torrent_action(self, action: str, hashes: list[str] | str) -> None:
        if isinstance(hashes, list):
            hashes = "|".join(hashes)
        await self._request(
            "POST",
            f"/torrents/{action}",
            data={"hashes": hashes},
        )

    async def start(self, hashes): await self._torrent_action("start", hashes)
    async def stop(self, hashes): await self._torrent_action("stop", hashes)
    async def recheck(self, hashes): await self._torrent_action("recheck", hashes)
    async def reannounce(self, hashes): await self._torrent_action("reannounce", hashes)

    async def delete(self, hashes, delete_files: bool = False) -> None:
        if isinstance(hashes, list):
            hashes = "|".join(hashes)
        await self._request(
            "POST",
            "/torrents/delete",
            data={
                "hashes": hashes,
                "deleteFiles": str(delete_files).lower(),
            },
        )

    async def set_category(self, hashes, category: str) -> None:
        if isinstance(hashes, list):
            hashes = "|".join(hashes)
        await self._request(
            "POST",
            "/torrents/setCategory",
            data={"hashes": hashes, "category": category},
        )

    async def set_tags(self, hashes, tags: list[str]) -> None:
        if isinstance(hashes, list):
            hashes = "|".join(hashes)
        await self._request(
            "POST",
            "/torrents/addTags",
            data={"hashes": hashes, "tags": ",".join(tags)},
        )

    async def remove_tags(self, hashes, tags: list[str]) -> None:
        if isinstance(hashes, list):
            hashes = "|".join(hashes)
        await self._request(
            "POST",
            "/torrents/removeTags",
            data={"hashes": hashes, "tags": ",".join(tags)},
        )

    async def set_download_limit(self, hashes, limit: int) -> None:
        if isinstance(hashes, list):
            hashes = "|".join(hashes)
        await self._request(
            "POST",
            "/torrents/setDownloadLimit",
            data={"hashes": hashes, "limit": int(limit)},
        )

    async def set_upload_limit(self, hashes, limit: int) -> None:
        if isinstance(hashes, list):
            hashes = "|".join(hashes)
        await self._request(
            "POST",
            "/torrents/setUploadLimit",
            data={"hashes": hashes, "limit": int(limit)},
        )

    async def set_priority(self, hashes, priority: str) -> None:
        mapping = {
            "increase": "increasePrio",
            "decrease": "decreasePrio",
            "top": "topPrio",
            "bottom": "bottomPrio",
        }
        if priority not in mapping:
            raise ValueError(f"Unsupported priority operation: {priority}")
        await self._torrent_action(mapping[priority], hashes)

    async def set_force_start(self, hashes, value: bool) -> None:
        if isinstance(hashes, list):
            hashes = "|".join(hashes)
        await self._request(
            "POST",
            "/torrents/setForceStart",
            data={"hashes": hashes, "value": str(value).lower()},
        )

    async def toggle_sequential_download(self, hashes) -> None:
        await self._torrent_action("toggleSequentialDownload", hashes)

    async def set_super_seeding(self, hashes, value: bool) -> None:
        if isinstance(hashes, list):
            hashes = "|".join(hashes)
        await self._request(
            "POST",
            "/torrents/setSuperSeeding",
            data={"hashes": hashes, "value": str(value).lower()},
        )

    async def set_location(self, hashes, location: str) -> None:
        if isinstance(hashes, list):
            hashes = "|".join(hashes)
        await self._request(
            "POST",
            "/torrents/setLocation",
            data={"hashes": hashes, "location": location},
        )

    async def rename(self, torrent_hash: str, name: str) -> None:
        await self._request(
            "POST",
            "/torrents/rename",
            data={"hash": torrent_hash, "name": name},
        )

    async def categories(self) -> dict[str, Any]:
        return await self._request("GET", "/torrents/categories")

    async def tags(self) -> list[str]:
        result = await self._request("GET", "/torrents/tags")
        return [str(item) for item in result]

    async def files(self, torrent_hash: str) -> list[dict[str, Any]]:
        return await self._request(
            "GET",
            "/torrents/files",
            params={"hash": torrent_hash},
        )

    async def trackers(self, torrent_hash: str) -> list[dict[str, Any]]:
        return await self._request(
            "GET",
            "/torrents/trackers",
            params={"hash": torrent_hash},
        )