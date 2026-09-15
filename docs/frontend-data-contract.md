# Lovelace card data contract — v0.4

The card MUST NOT call qBittorrent WebAPI directly.

## Source

The card consumes Home Assistant entity state and calls Home Assistant services.

## Torrent identity

`hash` is the only command identity.

Names are display-only and MUST NOT be used to target commands.

## Required torrent fields

The normalized backend model provides:

- hash
- name
- state
- progress
- size
- total_size
- amount_left
- downloaded
- uploaded
- download_speed
- upload_speed
- eta
- ratio
- category
- tags
- save_path
- num_seeds
- num_leechs
- availability
- priority
- auto_tmm
- super_seeding
- sequential_download
- first_last_piece_prio

## Commands

The first card implementation should map UI operations to HA services:

- qbittorrent.start_torrent
- qbittorrent.stop_torrent
- qbittorrent_enhanced.recheck_torrent
- qbittorrent_enhanced.reannounce_torrent
- qbittorrent_enhanced.delete_torrent
- qbittorrent.set_category
- qbittorrent.set_tags
- qbittorrent.remove_tags
- qbittorrent.set_download_limit
- qbittorrent.set_upload_limit
- qbittorrent.set_priority
- qbittorrent.set_force_start
- qbittorrent.set_location
- qbittorrent.rename_torrent

Destructive delete-with-files requires explicit confirmation.

## Details view

Files and trackers are deliberately not exposed as HA entities.
They are intended for an on-demand details dialog in Phase 2.
