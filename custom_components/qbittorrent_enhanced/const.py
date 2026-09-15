from typing import Final

DOMAIN: Final = "qbittorrent_enhanced"

CONF_HOST: Final = "host"
CONF_AUTH_METHOD: Final = "auth_method"
CONF_API_KEY: Final = "api_key"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_CONNECTION_SPEED_MBPS: Final = "connection_speed_mbps"
CONF_NAME: Final = "name"

AUTH_API_KEY: Final = "api_key"
AUTH_CREDENTIALS: Final = "credentials"

DEFAULT_UPDATE_INTERVAL: Final = 15
DEFAULT_VERIFY_SSL: Final = True
MIN_UPDATE_INTERVAL: Final = 5
MAX_UPDATE_INTERVAL: Final = 300

API_BASE: Final = "/api/v2"

ATTR_HASH: Final = "hash"
ATTR_HASHES: Final = "hashes"

SERVICE_START: Final = "start_torrent"
SERVICE_STOP: Final = "stop_torrent"
SERVICE_RECHECK: Final = "recheck_torrent"
SERVICE_REANNOUNCE: Final = "reannounce_torrent"
SERVICE_DELETE: Final = "delete_torrent"
SERVICE_SET_CATEGORY: Final = "set_category"
SERVICE_ADD_MAGNET: Final = "add_magnet"

SERVICE_HASH: Final = "hash"
SERVICE_HASHES: Final = "hashes"
SERVICE_DELETE_FILES: Final = "delete_files"
SERVICE_CATEGORY: Final = "category"
