from playout_lib import config


def test_media_location_keeps_urls_for_development(monkeypatch):
    monkeypatch.setattr(config, "MEDIA_ROOT", "")

    assert config.media_location("https://frikanalen.no/media/video.mp4") == (
        "https://frikanalen.no/media/video.mp4"
    )


def test_media_location_maps_bare_filenames_to_the_media_mount(monkeypatch):
    monkeypatch.setattr(config, "MEDIA_ROOT", "/mnt/media")

    assert config.media_location("video/broadcast.mp4") == "/mnt/media/video/broadcast.mp4"


def test_media_location_handles_a_leading_slash(monkeypatch):
    monkeypatch.setattr(config, "MEDIA_ROOT", "/mnt/media")

    assert config.media_location("/video/broadcast.mp4") == "/mnt/media/video/broadcast.mp4"
