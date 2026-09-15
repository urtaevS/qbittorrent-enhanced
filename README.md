# qBittorrent Enhanced

A custom Home Assistant integration for controlling and monitoring a local qBittorrent server through the qBittorrent Web API.

> **Status:** custom integration for Home Assistant, distributed through GitHub and HACS.

## Features

- Home Assistant Config Flow setup.
- qBittorrent Web API key authentication on supported qBittorrent versions.
- Username/password authentication for legacy setups.
- Centralized polling through a `DataUpdateCoordinator`.
- Torrent monitoring with a normalized torrent data model.
- Torrent control actions based on torrent hash.
- Add torrents from Magnet links.
- Start, stop, recheck and reannounce torrents.
- Delete torrents and optionally delete their files.
- Category and tag management.
- Download/upload speed limits.
- Global and alternative speed-limit controls.
- Alternative-speed switch.
- Configurable connection speed used to constrain the speed-limit controls.
- Diagnostics with sensitive authentication data redacted.

## Requirements

- Home Assistant with support for custom integrations.
- qBittorrent with Web API access enabled.
- Network access from Home Assistant to the qBittorrent Web UI/API.

The integration does not communicate with qBittorrent from the Lovelace frontend. Home Assistant remains the API boundary.

## Installation with HACS

### Custom repository

Until the repository is accepted into the HACS default store, add it as a custom repository:

1. Open **HACS**.
2. Open **Integrations**.
3. Open the three-dot menu.
4. Select **Custom repositories**.
5. Enter:

   `https://github.com/YOUR_GITHUB_USERNAME/qbittorrent-enhanced`

6. Select **Integration** as the repository type.
7. Add the repository and install **qBittorrent Enhanced**.
8. Restart Home Assistant.

Replace `YOUR_GITHUB_USERNAME` with the GitHub account that owns this repository.

## Manual installation

Copy the integration directory to:

```text
/config/custom_components/qbittorrent_enhanced/
```

Then restart Home Assistant.

## Configuration

After installation:

1. Go to **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **qBittorrent Enhanced**.
4. Enter the qBittorrent connection details.
5. Optionally enter the Internet connection speed in Mbps. This is used to set a sensible upper bound for the speed-limit controls.

For example, a 300 Mbps connection corresponds to a theoretical maximum of 37.5 MB/s.

## Speed limits

The integration exposes speed limits in **MB/s**, while qBittorrent's API values remain in bytes per second internally.

Default UI limits are:

- Global download/upload: up to 150 MB/s.
- Alternative download/upload: up to 10 MB/s.

When a connection speed is configured, the global controls are additionally limited to the corresponding theoretical MB/s value.

The alternative limits are qBittorrent's lower-bandwidth profile. The alternative-speed switch controls whether that profile is active.

## Actions

The integration provides Home Assistant actions under the `qbittorrent_enhanced` namespace, including:

- `add_magnet`
- `get_torrents`
- `start_torrent`
- `stop_torrent`
- `recheck_torrent`
- `reannounce_torrent`
- `delete_torrent`
- `set_category`
- `set_tags`
- `remove_tags`
- `set_download_limit`
- `set_upload_limit`
- `set_priority`
- `set_force_start`
- `set_location`
- `rename_torrent`

The Home Assistant action editor obtains field definitions from `services.yaml`.

## qBittorrent Web API

The integration is designed around qBittorrent Web API v2 and includes compatibility handling for API versions where the newer speed-limit endpoints are not available.

API-key authentication is preferred on qBittorrent versions that support it; username/password authentication remains available as a fallback.

## Security

- Authentication credentials are stored in the Home Assistant config entry.
- Diagnostics redact authentication secrets.
- The integration uses Home Assistant's configuration and service/action layer rather than exposing qBittorrent credentials to the frontend.

## Development

The repository contains the Home Assistant integration under:

```text
custom_components/qbittorrent_enhanced/
```

Project tests are kept under `tests/`.

GitHub Actions validate the repository with both HACS validation and Home Assistant Hassfest.

## Version

Current release: **0.5.15**

## License

MIT License. See [LICENSE](LICENSE).

## Disclaimer

This is a community-maintained custom Home Assistant integration. It is not part of Home Assistant Core and is not affiliated with or endorsed by the qBittorrent project.
