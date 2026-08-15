from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playout_lib import api
from playout_lib.items import Graphic

from .factories import make_scheduleitem, make_video

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
