from playout_lib import config


def test_media_location_leaves_urls_untouched():
    assert config.media_location("https://frikanalen.no/media/video.mp4") == (
        "https://frikanalen.no/media/video.mp4"
    )


def test_media_location_leaves_bare_filenames_relative():
    assert config.media_location("video/broadcast.mp4") == "video/broadcast.mp4"


def test_media_location_strips_a_leading_slash():
    # CasparCG resolves PLAY/LOADBG filenames relative to its own configured
    # <media-path>, so a leading slash must not survive into an absolute path.
    assert config.media_location("/video/broadcast.mp4") == "video/broadcast.mp4"
