## 0.5.18

- Config Entry title now follows the Home Assistant device name.
- Removed the separate connection-name field from Config Flow and Options Flow.
- Existing connections are synchronized with their device name on setup and when the device is renamed.
- Multiple qBittorrent connections are therefore distinguishable by their HA device names (for example `NAS` and `Skynet`).

# Changelog

## 0.5.17

- Use the user-facing qBittorrent device name as the Home Assistant config-entry title.
- Keep the integration title synchronized when the device name is changed in Home Assistant.
- Multiple qBittorrent connections are now distinguishable by their device names.


## 0.5.16

- Added a configurable connection name during initial setup.
- The connection name is shown as the Home Assistant Config Entry title, making multiple qBittorrent servers easy to distinguish.
- Added the connection name to integration options so it can be changed later.

## 0.5.15 — 2026-09-11

- Prepared the repository for GitHub and HACS distribution.
- Added HACS and Hassfest GitHub Actions.
- Added repository-level HACS metadata and MIT license.
- Updated the integration manifest with documentation, issue tracker and codeowner metadata.
- Added current installation and configuration documentation.

## 0.5.5

- Treat a duplicate Magnet as `already_exists` when the existing torrent can be found by info hash.

# Changelog

## 0.4.0 — 2026-09-07

- Added diagnostics with secret redaction.
- Hardened coordinator/entity data access.
- Formalized normalized torrent data contract.
- Added Lovelace frontend data contract.
- Added explicit hub integration type.
- Kept torrent commands hash-based.

## 0.3.0

- Added normalized torrent model and torrent management operations.

## 0.2.0

- Added capability detection, speed limits, expanded entities and services.

## 0.1.0

- Initial API client / coordinator scaffold.

## 0.5.4
- Limit torrent addition to a single magnet link.
- Remove raw `.torrent` upload and HTTP/BC URL exposure from the current HA action.
- Rename the action/API method to `add_magnet`.

## 0.5.3
- Added `qbittorrent_enhanced.add_torrent` for HTTP(S), magnet and BC URLs.
- Added raw `.torrent` multipart support at the API layer for the future frontend upload flow.
- Added add-torrent options and optional response data.
- Fixed stale `qbittorrent` integration selectors in `services.yaml`.
- Kept compatibility with WebAPI 2.15.x while omitting `skip_checking` on WebAPI 2.16+ and supporting `seedMode` there.
