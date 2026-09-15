from custom_components.qbittorrent_enhanced.api import Torrent

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
