from unittest.mock import MagicMock

from custom_components.qbittorrent_enhanced.api import QBittorrentApi, Torrent


def test_api_key_header():
    api = QBittorrentApi(
        MagicMock(),
        "https://qbt.example",
        True,
        api_key="qbt_test_key",
    )
    assert api._headers() == {"Authorization": "Bearer qbt_test_key"}


def test_capabilities_216():
    api = QBittorrentApi(MagicMock(), "http://qbt", True)
    api.info = type("Info", (), {"webapi_version": "2.16.1"})()
    assert api.capabilities.speed_limits_v2 is True
    assert api.capabilities.api_key_auth is True


def test_capabilities_215():
    api = QBittorrentApi(MagicMock(), "http://qbt", True)
    api.info = type("Info", (), {"webapi_version": "2.15.1"})()
    assert api.capabilities.speed_limits_v2 is False
    assert api.capabilities.api_key_auth is True


def test_torrent_normalization():
    torrent = Torrent.from_api({
        "hash": "ABC",
        "name": "Example",
        "state": "downloading",
        "progress": 0.5,
        "dlspeed": 1000,
        "upspeed": 200,
        "tags": "one, two",
        "seq_dl": True,
    })
    assert torrent.hash == "ABC"
    assert torrent.progress == 0.5
    assert torrent.download_speed == 1000
    assert torrent.tags == ("one", "two")
    assert torrent.sequential_download is True


def test_add_magnet_rejects_non_magnet():
    import pytest
    api = QBittorrentApi(MagicMock(), "http://qbt", True)
    with pytest.raises(ValueError, match="magnet link"):
        __import__("asyncio").run(api.add_magnet(magnet_url="https://example.test/a.torrent"))


def test_add_magnet_rejects_empty():
    import pytest
    api = QBittorrentApi(MagicMock(), "http://qbt", True)
    with pytest.raises(ValueError, match="magnet link"):
        __import__("asyncio").run(api.add_magnet(magnet_url="  "))
