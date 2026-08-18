from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from frikanalen_django_api_client.types import UNSET
from playout_lib import video

from .factories import make_video, make_video_file_records

TZ = ZoneInfo("Europe/Oslo")
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=TZ)


@pytest.fixture(autouse=True)
def frozen_localtime(monkeypatch):
    monkeypatch.setattr(video, "localtime", lambda: NOW)


@pytest.fixture
def issued(monkeypatch):
    """Collect the AMCP commands sent to CasparCG instead of connecting to one."""
    from playout_lib import caspar_player

    commands = []

    async def fake_issue(cmd):
        commands.append(cmd)

    monkeypatch.setattr(caspar_player.current_player, "issue", fake_issue)
    return commands


async def noop():
    return None


def make_prerecorded(video_files=None, use_original=False, video_details=None, records=None):
    return video.PrerecordedVideo(
        1,
        "1-50",
        25000,
        NOW,
        NOW + timedelta(minutes=30),
        video_details=video_details,
        video_files=video_files,
        video_file_records=records,
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


class TestGainSelection:
    def test_uses_the_measurement_of_the_file_actually_played(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded(
            {"broadcast": "broadcast.mp4", "original": "original.mp4"},
            records=make_video_file_records(
                broadcast=(-27.0, -12.0),
                original=(-13.0, -12.0),
            ),
        )

        assert pv.gain_db == pytest.approx(4.0)

    def test_follows_use_original_to_the_other_measurement(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", True)
        pv = make_prerecorded(
            {"broadcast": "broadcast.mp4", "original": "original.mp4"},
            records=make_video_file_records(
                broadcast=(-27.0, -12.0),
                original=(-13.0, -12.0),
            ),
        )

        assert pv.gain_db == pytest.approx(-10.0)

    def test_no_gain_when_the_file_has_no_measurement(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded(
            {"broadcast": "broadcast.mp4"},
            records=make_video_file_records(broadcast=(UNSET, UNSET)),
        )

        assert pv.gain_db is None

    def test_no_gain_when_records_were_never_fetched(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded({"broadcast": "broadcast.mp4"}, records=None)

        assert pv.gain_db is None

    def test_no_gain_when_the_played_variant_has_no_record(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded(
            {"broadcast": "broadcast.mp4"},
            records=make_video_file_records(original=(-27.0, -12.0)),
        )

        assert pv.gain_db is None

    def test_no_gain_when_falling_back_to_filler(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded(
            video_files={}, records=make_video_file_records(broadcast=(-27.0, -12.0))
        )

        assert pv.filename == "filler/FrikanalenLoop.avi"
        assert pv.gain_db is None

    def test_normalization_can_be_switched_off(self, monkeypatch):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        monkeypatch.setattr(video, "LOUDNESS_NORMALIZATION", False)
        pv = make_prerecorded(
            {"broadcast": "broadcast.mp4"},
            records=make_video_file_records(broadcast=(-27.0, -12.0)),
        )

        assert pv.gain_db is None


class TestVolumeCommand:
    async def test_measured_file_is_played_through_its_gain(self, monkeypatch, issued):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded(
            {"broadcast": "broadcast.mp4"},
            records=make_video_file_records(broadcast=(-29.0, -12.0)),
        )

        await pv._set_playback_volume()

        # +6 dB, so a bit less than double amplitude.
        assert issued == ["MIXER 1-50 VOLUME 1.9953"]

    async def test_unmeasured_file_resets_the_layer_to_unity(self, monkeypatch, issued):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded({"broadcast": "broadcast.mp4"}, records={})

        await pv._set_playback_volume()

        assert issued == ["MIXER 1-50 VOLUME 1.0000"]

    async def test_volume_is_set_before_the_play_command(self, monkeypatch, issued):
        monkeypatch.setattr(video, "USE_ORIGINAL", False)
        pv = make_prerecorded(
            {"broadcast": "broadcast.mp4"},
            records=make_video_file_records(broadcast=(-29.0, -12.0)),
        )
        pv.has_been_prepared = True
        monkeypatch.setattr(pv, "_completion", noop)

        await pv.cue()

        assert issued[:2] == ["MIXER 1-50 VOLUME 1.9953", "PLAY 1-50"]
