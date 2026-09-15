# qBittorrent Enhanced

A custom Home Assistant integration for qBittorrent with an accompanying
Lovelace card.

## Features

### Home Assistant integration

-   qBittorrent WebAPI v2 support
-   API key authentication for supported qBittorrent versions
-   Username/password authentication as a fallback
-   Configurable polling interval
-   Optional connection speed setting
-   Global download/upload speed limit controls
-   Alternative (Turtle) speed limit controls
-   Torrent sensors and normalized torrent data
-   Home Assistant actions for common torrent operations
-   Support for qBittorrent 5.x

### Lovelace card

The project also includes a custom Lovelace card:

`qbittorrent-enhanced-card.js`

The card uses the Home Assistant qBittorrent Enhanced integration rather
than connecting directly to the qBittorrent WebAPI.

The card is intended to provide a convenient interface for viewing and
managing torrents from a Home Assistant dashboard.

## Installation

### Home Assistant integration

#### HACS

1.  Open **HACS** in Home Assistant.
2.  Open **Integrations**.
3.  Add this repository as a custom repository if it is not already
    available in HACS: `https://github.com/urtaevS/qbittorrent-enhanced`
4.  Select **Integration** as the category.
5.  Install **qBittorrent Enhanced**.
6.  Restart Home Assistant.
7.  Go to **Settings → Devices & services → Add integration**.
8.  Search for **qBittorrent Enhanced** and configure your qBittorrent
    server.

#### Manual installation

Copy the `custom_components/qbittorrent_enhanced` directory into:

``` text
/config/custom_components/qbittorrent_enhanced/
```

Restart Home Assistant and add the integration from **Settings → Devices
& services**.

---

### Lovelace card

#### HACS

The card is distributed from the same repository.

1.  Open **HACS → Frontend**.
2.  Open the menu in the top-right corner.
3.  Select **Custom repositories**.
4.  Add: `https://github.com/urtaevS/qbittorrent-enhanced`
5.  Select **Lovelace** as the repository category.
6.  Install the qBittorrent Enhanced card.
7.  Restart Home Assistant if requested.

The card file is:

``` text
frontend/qbittorrent-enhanced-card.js
```

#### Manual installation

Copy:

``` text
frontend/qbittorrent-enhanced-card.js
```

to:

``` text
/config/www/qbittorrent-enhanced/
```

Then add the JavaScript module as a Lovelace resource:

``` yaml
url: /local/qbittorrent-enhanced/qbittorrent-enhanced-card.js
type: module
```

After adding the resource, the card can be added to a Lovelace
dashboard.

## Configuration

Configure the qBittorrent Enhanced integration through the Home
Assistant UI.

The initial setup supports:

-   qBittorrent host
-   API key or username/password authentication
-   SSL verification
-   Update interval
-   Optional internet connection speed

The connection speed is used to determine the maximum values exposed by
the global and alternative speed-limit number entities.

### Speed limits

Speed-limit entities use **MB/s** in Home Assistant.

Global limits:

-   Default maximum without a configured connection speed: `150 MB/s`
-   With a configured connection speed, the maximum is limited by the
    connection speed

Alternative limits:

-   Default maximum: `10 MB/s`
-   If the configured connection speed is below `80 Mbps`, the maximum
    is limited accordingly

`0 MB/s` means unlimited.

## Actions

The integration provides Home Assistant actions for common torrent
operations, including:

-   `qbittorrent_enhanced.add_magnet`
-   `qbittorrent_enhanced.get_torrents`
-   `qbittorrent_enhanced.start_torrent`
-   `qbittorrent_enhanced.stop_torrent`
-   `qbittorrent_enhanced.recheck_torrent`
-   `qbittorrent_enhanced.reannounce_torrent`
-   `qbittorrent_enhanced.delete_torrent`
-   `qbittorrent_enhanced.set_category`
-   `qbittorrent_enhanced.set_tags`
-   `qbittorrent_enhanced.remove_tags`
-   `qbittorrent_enhanced.set_download_limit`
-   `qbittorrent_enhanced.set_upload_limit`
-   `qbittorrent_enhanced.set_priority`
-   `qbittorrent_enhanced.set_force_start`
-   `qbittorrent_enhanced.set_location`
-   `qbittorrent_enhanced.rename_torrent`

`add_magnet` accepts a magnet link directly. Redirect URLs are not
resolved by the integration.

## Security

The integration communicates with qBittorrent locally through its
WebAPI.

-   API keys and credentials are not intended to be logged.
-   SSL certificate verification can be configured during setup.
-   Use HTTPS when communicating with qBittorrent over an untrusted
    network.

## Development

The repository contains the Home Assistant integration under:

``` text
custom_components/qbittorrent_enhanced/
```

The Lovelace card is under:

``` text
frontend/
```

The project also contains tests and GitHub validation workflows.

## Version

Current release: **0.5.18**

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Disclaimer

This is a custom Home Assistant integration and Lovelace card. It is not
affiliated with or endorsed by the qBittorrent project.
