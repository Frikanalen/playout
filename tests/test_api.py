from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from playout_lib import api
from playout_lib.items import FillerLoop, Graphic

from .factories import make_scheduleitem, make_video, make_video_file_records

TZ = ZoneInfo("Europe/Oslo")


def at(minutes):
    return datetime(2026, 1, 1, 10, 0, tzinfo=TZ) + timedelta(minutes=minutes)


class FakeScheduleFetcher:
    def __init__(self, items):
        self._items = items

    def __call__(self, client):
        return self

    async def get_schedule(self, date="today", days=1, surrounding=False):
        return self._items


def install_fetcher(monkeypatch, items):
    monkeypatch.setattr(api, "ScheduleFetcher", FakeScheduleFetcher(items))


def install_video_details(monkeypatch, videos_by_id, calls=None):
    async def fake_get_video_details(video_id, client):
        if calls is not None:
            calls.append(video_id)
        return videos_by_id.get(video_id)

    monkeypatch.setattr(api, "get_video_details", fake_get_video_details)


@pytest.fixture(autouse=True)
def no_file_records(monkeypatch):
    """Keep the loudness lookup off the network unless a test opts in."""
    install_file_records(monkeypatch, {})


def install_file_records(monkeypatch, records_by_id, fails=()):
    async def fake_get_video_file_records(video_id, client):
        if video_id in fails:
            raise RuntimeError("API is having a day")
        return records_by_id.get(video_id, {})

    monkeypatch.setattr(api, "get_video_file_records", fake_get_video_file_records)


class TestLoadSchedule:
    async def test_builds_prerecorded_videos_from_schedule_items(self, monkeypatch):
        items = [
            make_scheduleitem(1, 1, at(0), at(30)),
            make_scheduleitem(2, 2, at(35), at(65)),
        ]
        videos = {
            1: make_video(1, framerate=25000, broadcast="video1.mp4"),
            2: make_video(2, framerate=25000, broadcast="video2.mp4"),
        }
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, videos)

        schedule = await api.load_schedule()

        video_items = [i for i in schedule if hasattr(i, "video_id")]
        assert [v.video_id for v in video_items] == [1, 2]
        assert video_items[0].filename == "video1.mp4"

    async def test_inserts_graphic_into_gap_between_videos(self, monkeypatch):
        items = [
            make_scheduleitem(1, 1, at(0), at(30)),
            make_scheduleitem(2, 2, at(35), at(65)),
        ]
        videos = {
            1: make_video(1, broadcast="video1.mp4"),
            2: make_video(2, broadcast="video2.mp4"),
        }
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, videos)

        schedule = await api.load_schedule()

        graphics = [i for i in schedule if isinstance(i, Graphic)]
        assert len(graphics) == 1
        assert graphics[0].start_time == at(30)
        assert graphics[0].end_time == at(35)
        assert "duration=300000" in graphics[0].url  # 5 minutes in ms

    async def test_uses_filler_loop_for_gaps_under_30_seconds(self, monkeypatch):
        items = [
            make_scheduleitem(1, 1, at(0), at(30)),
            make_scheduleitem(2, 2, at(30) + timedelta(seconds=20), at(65)),
        ]
        videos = {
            1: make_video(1, broadcast="video1.mp4"),
            2: make_video(2, broadcast="video2.mp4"),
        }
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, videos)

        schedule = await api.load_schedule()

        fillers = [i for i in schedule if isinstance(i, FillerLoop)]
        assert len(fillers) == 1
        assert fillers[0].start_time == at(30)
        assert fillers[0].end_time == at(30) + timedelta(seconds=20)
        assert not any(isinstance(i, Graphic) for i in schedule)

    async def test_uses_graphic_for_gap_of_exactly_30_seconds(self, monkeypatch):
        items = [
            make_scheduleitem(1, 1, at(0), at(30)),
            make_scheduleitem(2, 2, at(30) + timedelta(seconds=30), at(65)),
        ]
        videos = {
            1: make_video(1, broadcast="video1.mp4"),
            2: make_video(2, broadcast="video2.mp4"),
        }
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, videos)

        schedule = await api.load_schedule()

        assert any(isinstance(i, Graphic) for i in schedule)
        assert not any(isinstance(i, FillerLoop) for i in schedule)

    async def test_result_is_sorted_by_start_time(self, monkeypatch):
        items = [
            make_scheduleitem(1, 1, at(0), at(30)),
            make_scheduleitem(2, 2, at(35), at(65)),
        ]
        videos = {
            1: make_video(1, broadcast="video1.mp4"),
            2: make_video(2, broadcast="video2.mp4"),
        }
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, videos)

        schedule = await api.load_schedule()

        assert schedule == sorted(schedule, key=lambda i: i.start_time)

    async def test_video_details_are_fetched_once_per_unique_video(self, monkeypatch):
        items = [
            make_scheduleitem(1, 1, at(0), at(30)),
            make_scheduleitem(2, 1, at(30), at(60)),  # same video_id=1 twice
        ]
        videos = {1: make_video(1, broadcast="video1.mp4")}
        calls = []
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, videos, calls=calls)

        await api.load_schedule()

        assert calls == [1]

    async def test_falls_back_to_default_framerate_when_video_details_missing(self, monkeypatch):
        items = [make_scheduleitem(1, 1, at(0), at(30))]
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, {})  # video 1 not found

        schedule = await api.load_schedule()

        video_items = [i for i in schedule if hasattr(i, "video_id")]
        assert video_items[0].framerate == 25.0  # 25000 / 1000 default


class TestLoudnessRecords:
    async def test_attaches_file_records_to_their_video(self, monkeypatch):
        items = [make_scheduleitem(1, 1, at(0), at(30))]
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, {1: make_video(1, broadcast="video1.mp4")})
        install_file_records(monkeypatch, {1: make_video_file_records(broadcast=(-27.0, -12.0))})

        schedule = await api.load_schedule()

        video_item = next(i for i in schedule if hasattr(i, "video_id"))
        assert video_item.gain_db == pytest.approx(4.0)

    async def test_a_failed_lookup_leaves_the_video_playable(self, monkeypatch):
        items = [make_scheduleitem(1, 1, at(0), at(30))]
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, {1: make_video(1, broadcast="video1.mp4")})
        install_file_records(monkeypatch, {}, fails={1})

        schedule = await api.load_schedule()

        video_item = next(i for i in schedule if hasattr(i, "video_id"))
        assert video_item.filename == "video1.mp4"
        assert video_item.gain_db is None
