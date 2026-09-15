import pytest

from custom_components.qbittorrent_enhanced.api import QBittorrentApi


@pytest.mark.asyncio
async def test_add_magnet_payload():
    api = QBittorrentApi(None, "http://qbt", True)
    api.info = type("Info", (), {"webapi_version": "2.15.1"})()
    captured = {}

    async def fake_request(method, path, **kwargs):
        captured.update(method=method, path=path, data=kwargs["data"])
        return {"success_count": 1, "pending_count": 0, "failure_count": 0, "added_torrent_ids": ["abc"]}

    api._request = fake_request
    result = await api.add_magnet(
        magnet_url="  magnet:?xt=urn:btih:abc  ",
        save_path="/downloads",
        paused=True,
        tags=["music", "test"],
        skip_checking=True,
    )

    assert captured["method"] == "POST"
    assert captured["path"] == "/torrents/add"
    assert captured["data"]["urls"] == "magnet:?xt=urn:btih:abc"
    assert captured["data"]["savepath"] == "/downloads"
    assert captured["data"]["paused"] == "true"
    assert captured["data"]["skip_checking"] == "true"
    assert captured["data"]["tags"] == "music,test"
    assert result["added_torrent_ids"] == ["abc"]


@pytest.mark.asyncio
async def test_add_magnet_rejects_non_magnet():
    api = QBittorrentApi(None, "http://qbt", True)
    with pytest.raises(ValueError, match="magnet link"):
        await api.add_magnet(magnet_url="https://example.test/a.torrent")
