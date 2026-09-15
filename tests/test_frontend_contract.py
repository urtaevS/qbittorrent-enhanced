from dataclasses import asdict

from custom_components.qbittorrent_enhanced.api import Torrent


def test_torrent_contract_is_json_friendly():
    torrent = Torrent.from_api({
        "hash": "ABC",
        "name": "Example",
        "tags": "linux, iso",
        "progress": 0.5,
        "dlspeed": 123,
    })
    payload = {**asdict(torrent), "tags": list(torrent.tags)}
    assert payload["hash"] == "ABC"
    assert payload["tags"] == ["iso", "linux"]
    assert payload["download_speed"] == 123
