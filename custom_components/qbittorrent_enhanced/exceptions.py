class QBittorrentError(Exception):
    """Base qBittorrent error."""


class QBittorrentDuplicateError(QBittorrentError):
    """qBittorrent reports that a torrent already exists."""


class QBittorrentAuthError(QBittorrentError):
    """Authentication failed."""


class QBittorrentApiError(QBittorrentError):
    """WebAPI returned an error."""


class QBittorrentConnectionError(QBittorrentError):
    """Could not communicate with qBittorrent."""
