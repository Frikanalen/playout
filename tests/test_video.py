from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from playout_lib import video

from .factories import make_video

TZ = ZoneInfo("Europe/Oslo")
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=TZ)


@pytest.fixture(autouse=True)
def frozen_localtime(monkeypatch):
    monkeypatch.setattr(video, "localtime", lambda: NOW)


def make_prerecorded(video_files=None, use_original=False, video_details=None):
    return video.PrerecordedVideo(
        1,
        "1-50",
        25000,
        NOW,
        NOW + timedelta(minutes=30),
        video_details=video_details,
        video_files=video_files,
    )


class TestFilenameSelection:
    def test_prefers_broadcast_when_not_use_original(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded({"broadcast": "broadcast.mp4", "original": "original.mp4"})

        assert pv.filename == "broadcast.mp4"

    def test_falls_back_to_original_when_no_broadcast(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded({"original": "original.mp4"})

        assert pv.filename == "original.mp4"

    def test_prefers_original_when_use_original(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", True)
        pv = make_prerecorded({"broadcast": "broadcast.mp4", "original": "original.mp4"})

        assert pv.filename == "original.mp4"

    def test_falls_back_to_broadcast_when_use_original_and_no_original(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", True)
        pv = make_prerecorded({"broadcast": "broadcast.mp4"})

        assert pv.filename == "broadcast.mp4"

    def test_falls_back_to_filler_when_no_video_files_at_all(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded(video_files=None)

        assert pv.filename == "filler/FrikanalenLoop.avi"

    def test_falls_back_to_filler_when_video_files_empty(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded(video_files={})

        assert pv.filename == "filler/FrikanalenLoop.avi"

    def test_filename_is_cached_after_first_access(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        files = {"broadcast": "broadcast.mp4"}
        pv = make_prerecorded(files)

        assert pv.filename == "broadcast.mp4"
        files["broadcast"] = "changed.mp4"

        assert pv.filename == "broadcast.mp4"


class TestFramerate:
    def test_framerate_is_scaled_from_millihertz(self):
        pv = make_prerecorded({"broadcast": "broadcast.mp4"})

        assert pv.framerate == 25.0


class TestEnsureFilesLoaded:
    async def test_fetches_details_when_not_pre_supplied(self, monkeypatch):
        fetched_video = make_video(1, framerate=30000, broadcast="fetched.mp4")

        async def fake_get_video_details(video_id):
            return fetched_video

        monkeypatch.setattr(video, "get_video_details", fake_get_video_details)

        pv = make_prerecorded(video_files=None, video_details=None)
        await pv.ensure_files_loaded()

        assert pv.framerate == 30.0
        assert pv.filename == "fetched.mp4"

    async def test_does_not_refetch_when_already_supplied(self, monkeypatch):
        async def boom(video_id):
            raise AssertionError("should not be called")

        monkeypatch.setattr(video, "get_video_details", boom)

        pv = make_prerecorded(
            video_files={"broadcast": "broadcast.mp4"}, video_details="already-set"
        )
        await pv.ensure_files_loaded()

        assert pv.filename == "broadcast.mp4"
