from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from playout_lib import api
from playout_lib.items import FillerLoop, Graphic, Poster, ProgrammeUnavailable
from playout_lib.live import LiveTransmission
from playout_lib.scheduler import item_key
from playout_lib.video import PrerecordedVideo

from .factories import make_poster_item, make_scheduleitem, make_video, make_video_file_records

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
def today(monkeypatch):
    """Load the schedule as if it were 1 January, the day the tests book."""
    monkeypatch.setattr(api, "localtime", lambda: at(0))


def between(schedule, start, end):
    """The items that start inside [start, end)."""
    return [i for i in schedule if start <= i.start_time < end]


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

        graphics = [i for i in between(schedule, at(0), at(65)) if isinstance(i, Graphic)]
        assert len(graphics) == 1
        assert graphics[0].start_time == at(30)
        assert graphics[0].end_time == at(35)
        assert "duration=300000" in graphics[0].url  # 5 minutes in ms

    async def test_uses_configured_graphics_url(self, monkeypatch):
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
        monkeypatch.setattr(api, "GRAPHICS_URL", "https://staging.frikanalen.tv/graphics/")

        schedule = await api.load_schedule()

        graphic = next(i for i in between(schedule, at(0), at(65)) if isinstance(i, Graphic))
        assert graphic.url == "https://staging.frikanalen.tv/graphics/?duration=300000"

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

        middle = between(schedule, at(0), at(65))
        fillers = [i for i in middle if isinstance(i, FillerLoop)]
        assert len(fillers) == 1
        assert fillers[0].start_time == at(30)
        assert fillers[0].end_time == at(30) + timedelta(seconds=20)
        assert not any(isinstance(i, Graphic) for i in middle)

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


class TestLiveTransmissions:
    STREAM_ID = UUID("6f1c2d6e-8a1b-4c3d-9e2f-0a1b2c3d4e5f")

    async def test_a_live_slot_plays_its_source(self, monkeypatch):
        items = [make_scheduleitem(1, 1, at(0), at(30), live_stream_id=self.STREAM_ID)]
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, {})

        schedule = between(await api.load_schedule(), at(0), at(30))

        assert len(schedule) == 1
        assert isinstance(schedule[0], LiveTransmission)
        assert schedule[0].path == f"contrib/live/{self.STREAM_ID}"
        assert schedule[0].start_time == at(0)
        assert schedule[0].end_time == at(30)

    async def test_a_live_slot_fetches_no_video_files(self, monkeypatch):
        items = [
            make_scheduleitem(1, 1, at(0), at(30)),
            make_scheduleitem(2, 2, at(30), at(60), live_stream_id=self.STREAM_ID),
        ]
        calls = []
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, {1: make_video(1, broadcast="v.mp4")}, calls=calls)

        await api.load_schedule()

        assert calls == [1]

    async def test_gaps_around_a_live_slot_get_graphics(self, monkeypatch):
        items = [
            make_scheduleitem(1, 1, at(0), at(30), live_stream_id=self.STREAM_ID),
            make_scheduleitem(2, 2, at(35), at(65)),
        ]
        install_fetcher(monkeypatch, items)
        install_video_details(monkeypatch, {2: make_video(2, broadcast="v.mp4")})

        schedule = between(await api.load_schedule(), at(0), at(65))

        assert [type(i) for i in schedule] == [LiveTransmission, Graphic, PrerecordedVideo]

    async def test_skips_an_item_with_neither_video_nor_source(self, monkeypatch):
        item = make_scheduleitem(1, 1, at(0), at(30))
        item.video = None
        install_fetcher(monkeypatch, [item, make_scheduleitem(2, 2, at(35), at(65))])
        install_video_details(monkeypatch, {2: make_video(2, broadcast="v.mp4")})

        schedule = await api.load_schedule()

        assert [i.video_id for i in schedule if hasattr(i, "video_id")] == [2]


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


MIDNIGHT = datetime(2026, 1, 1, tzinfo=TZ)


class TestUnprogrammedTime:
    """Graphics cover everything the schedule leaves empty."""

    async def test_a_day_with_nothing_scheduled_is_all_graphics(self, monkeypatch):
        install_fetcher(monkeypatch, [])
        install_video_details(monkeypatch, {})

        schedule = await api.load_schedule()

        assert len(schedule) == 1
        assert isinstance(schedule[0], Graphic)
        assert schedule[0].start_time == MIDNIGHT
        assert schedule[0].end_time == MIDNIGHT + api.LOOKAHEAD

    async def test_graphics_before_the_first_and_after_the_last_programme(self, monkeypatch):
        install_fetcher(monkeypatch, [make_scheduleitem(1, 1, at(0), at(30))])
        install_video_details(monkeypatch, {1: make_video(1, broadcast="v.mp4")})

        schedule = await api.load_schedule()

        assert [type(i) for i in schedule] == [Graphic, PrerecordedVideo, Graphic]
        assert (schedule[0].start_time, schedule[0].end_time) == (MIDNIGHT, at(0))
        assert (schedule[2].start_time, schedule[2].end_time) == (at(30), MIDNIGHT + api.LOOKAHEAD)

    async def test_the_gap_after_yesterdays_last_programme_starts_where_it_ended(self, monkeypatch):
        # The item before today comes along, so the overnight graphic keeps
        # its start across the midnight reload and stays on air.
        yesterday = make_scheduleitem(1, 1, at(-14 * 60), at(-13 * 60))
        install_fetcher(monkeypatch, [yesterday, make_scheduleitem(2, 2, at(0), at(30))])
        install_video_details(
            monkeypatch,
            {1: make_video(1, broadcast="a.mp4"), 2: make_video(2, broadcast="b.mp4")},
        )

        schedule = await api.load_schedule()

        overnight = schedule[1]
        assert isinstance(overnight, Graphic)
        assert (overnight.start_time, overnight.end_time) == (at(-13 * 60), at(0))

    async def test_back_to_back_programmes_leave_no_gap(self, monkeypatch):
        install_fetcher(
            monkeypatch,
            [make_scheduleitem(1, 1, at(0), at(30)), make_scheduleitem(2, 2, at(30), at(60))],
        )
        install_video_details(
            monkeypatch,
            {1: make_video(1, broadcast="a.mp4"), 2: make_video(2, broadcast="b.mp4")},
        )

        schedule = between(await api.load_schedule(), at(0), at(60))

        assert [type(i) for i in schedule] == [PrerecordedVideo, PrerecordedVideo]


class TestMissingFiles:
    """A listed video whose file never arrived airs a notice for its slot."""

    async def test_a_video_without_a_file_shows_a_notice(self, monkeypatch):
        install_fetcher(monkeypatch, [make_scheduleitem(1, 1, at(0), at(30))])
        install_video_details(monkeypatch, {1: make_video(1)})

        schedule = between(await api.load_schedule(), at(0), at(30))

        assert len(schedule) == 1
        notice = schedule[0]
        assert isinstance(notice, ProgrammeUnavailable)
        assert notice.layer == api.NOTICE_LAYER
        assert (notice.start_time, notice.end_time) == (at(0), at(30))
        assert (
            notice.url == "https://frikanalen.tv/graphics/?duration=1800000&unavailable=Test+Video"
        )

    async def test_unknown_files_are_tried_rather_than_given_up(self, monkeypatch):
        # Details that failed to load say nothing about the file.
        install_fetcher(monkeypatch, [make_scheduleitem(1, 1, at(0), at(30))])
        install_video_details(monkeypatch, {})

        schedule = between(await api.load_schedule(), at(0), at(30))

        assert [type(i) for i in schedule] == [PrerecordedVideo]

    async def test_a_file_in_the_records_counts(self, monkeypatch):
        install_fetcher(monkeypatch, [make_scheduleitem(1, 1, at(0), at(30))])
        install_video_details(monkeypatch, {1: make_video(1)})
        install_file_records(monkeypatch, {1: make_video_file_records(broadcast=(-23.0, -3.0))})

        schedule = between(await api.load_schedule(), at(0), at(30))

        assert [type(i) for i in schedule] == [PrerecordedVideo]

    async def test_back_to_back_missing_programmes_share_one_notice(self, monkeypatch):
        install_fetcher(
            monkeypatch,
            [
                make_scheduleitem(1, 1, at(0), at(30)),
                make_scheduleitem(2, 2, at(30), at(60)),
                make_scheduleitem(3, 3, at(60), at(90)),
            ],
        )
        install_video_details(monkeypatch, {n: make_video(n) for n in (1, 2, 3)})

        schedule = between(await api.load_schedule(), at(0), at(90))

        assert len(schedule) == 1
        assert isinstance(schedule[0], ProgrammeUnavailable)
        assert schedule[0].end_time == at(90)
        assert schedule[0].url.endswith("duration=5400000&unavailable=")

    async def test_gaps_around_a_notice_get_graphics(self, monkeypatch):
        install_fetcher(
            monkeypatch,
            [make_scheduleitem(1, 1, at(0), at(30)), make_scheduleitem(2, 2, at(35), at(65))],
        )
        install_video_details(monkeypatch, {1: make_video(1, broadcast="a.mp4"), 2: make_video(2)})

        schedule = between(await api.load_schedule(), at(0), at(65))

        assert [type(i) for i in schedule] == [PrerecordedVideo, Graphic, ProgrammeUnavailable]
        assert schedule[1].layer != schedule[2].layer


class TestPosters:
    """A member's text poster airs the graphics template with its text."""

    async def test_a_poster_shows_its_text_for_its_slot(self, monkeypatch):
        install_fetcher(
            monkeypatch,
            [
                make_scheduleitem(1, 1, at(0), at(20)),
                make_poster_item(2, at(20), at(21), heading="Neste: debatt", text="Kl. 20 & 21"),
                make_scheduleitem(3, 3, at(25), at(55)),
            ],
        )
        videos = {n: make_video(n, broadcast=f"{n}.mp4") for n in (1, 3)}
        calls = []
        install_video_details(monkeypatch, videos, calls)

        schedule = between(await api.load_schedule(), at(0), at(55))

        assert [type(i) for i in schedule] == [PrerecordedVideo, Poster, Graphic, PrerecordedVideo]
        poster = schedule[1]
        assert poster.layer == api.POSTER_LAYERS[0]
        assert (poster.start_time, poster.end_time) == (at(20), at(21))
        assert poster.url == (
            "https://frikanalen.tv/graphics/?duration=60000&poster=paper"
            "&heading=Neste%3A+debatt&text=Kl.+20+%26+21&from=Test+Org"
        )
        # No video details are fetched for a poster.
        assert sorted(calls) == [1, 3]

    async def test_back_to_back_posters_take_turns_on_two_layers(self, monkeypatch):
        install_fetcher(
            monkeypatch,
            [make_poster_item(n, at(n), at(n + 1)) for n in (0, 1, 2)]
            + [make_poster_item(9, at(5), at(6))],
        )
        install_video_details(monkeypatch, {})

        schedule = between(await api.load_schedule(), at(0), at(6))
        posters = [i for i in schedule if isinstance(i, Poster)]

        first, second = api.POSTER_LAYERS
        assert [p.layer for p in posters] == [first, second, first, first]

    async def test_a_corrected_poster_is_a_new_item(self, monkeypatch):
        install_fetcher(monkeypatch, [make_poster_item(1, at(0), at(1), text="Feil")])
        install_video_details(monkeypatch, {})
        [before] = [i for i in await api.load_schedule() if isinstance(i, Poster)]
        install_fetcher(monkeypatch, [make_poster_item(1, at(0), at(1), text="Riktig")])
        [after] = [i for i in await api.load_schedule() if isinstance(i, Poster)]

        assert item_key(before) != item_key(after)
