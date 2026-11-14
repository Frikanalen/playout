import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from playout_lib import watchdog
from playout_lib.caspar_player import CasparConnectionLost
from playout_lib.video import PrerecordedVideo
from playout_lib.watchdog import AirWatchdog, read_foreground

TZ = ZoneInfo("Europe/Oslo")
START = datetime(2026, 1, 1, 12, 0, tzinfo=TZ)


def channel(layers):
    """INFO 1 as CasparCG 2.5 sends it, for {number: foreground XML}."""
    xml = "".join(
        f"<layer_{n}><foreground>{fg}</foreground><background><producer>empty</producer>"
        f"</background></layer_{n}>"
        for n, fg in layers.items()
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\r\n'
        f"<channel><framerate>50</framerate><stage><layer>{xml}</layer></stage></channel>\r\n"
    )


def playing(path="/mnt/media/broadcast/1/clip.mxf", position=60.0, duration=1800.0, paused=False):
    return (
        f"<file><name>clip</name><path>{path}</path>"
        f"<time>{position}</time><time>{duration}</time></file>"
        f"<loop>false</loop><paused>{str(paused).lower()}</paused><producer>ffmpeg</producer>"
    )


EMPTY = "<producer>empty</producer><paused>false</paused>"


class FakeTask:
    def __init__(self, done=False):
        self._done = done

    def done(self):
        return self._done


class FakeScheduler:
    def __init__(self, *items):
        self.tasks = {i: (item, FakeTask()) for i, item in enumerate(items)}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def video_on_air(filename="broadcast/1/clip.mxf"):
    item = PrerecordedVideo(
        1,
        "1-50",
        25000,
        START,
        START + timedelta(minutes=30),
        video_files={"broadcast": filename},
    )
    item.on_air = True
    return item


@pytest.fixture
def now(monkeypatch):
    """Five minutes into the video's slot."""
    moment = {"t": START + timedelta(minutes=5)}
    monkeypatch.setattr(watchdog, "localtime", lambda: moment["t"])
    return moment


@pytest.fixture(autouse=True)
def no_recent_restart(monkeypatch):
    monkeypatch.delenv(watchdog.LAST_RESTART_ENV, raising=False)


def run_checks(dog, clock, infos, step=1.0):
    for info in infos:
        dog.check(info)
        clock.now += step


class TestReadForeground:
    def test_reads_a_playing_file(self):
        fg = read_foreground(channel({50: playing(position=61.5)}), "1-50")

        assert fg.producer == "ffmpeg"
        assert fg.path == "/mnt/media/broadcast/1/clip.mxf"
        assert (fg.time, fg.duration, fg.paused) == (61.5, 1800.0, False)

    def test_an_empty_producer_is_an_empty_layer(self):
        assert read_foreground(channel({50: EMPTY}), "1-50") is None

    def test_a_missing_layer_is_an_empty_layer(self):
        # What a freshly restarted CasparCG reports: only the channel bug.
        assert read_foreground(channel({100: playing()}), "1-50") is None

    @pytest.mark.parametrize("info", [None, "", "not xml", "<channel></channel>", ["list"]])
    def test_an_unreadable_answer_is_never_an_empty_layer(self, info):
        with pytest.raises(Exception):  # noqa: B017
            read_foreground(info, "1-50")


class TestWatchdog:
    def make(self, *items):
        clock = Clock()
        return AirWatchdog(FakeScheduler(*items), player=None, clock=clock), clock

    def test_all_is_well_while_the_video_plays(self, now):
        dog, clock = self.make(video_on_air())

        run_checks(dog, clock, [channel({50: playing(position=60 + i)}) for i in range(20)])

        assert not dog.restart.is_set()

    def test_restarts_when_the_layer_stays_empty(self, now):
        dog, clock = self.make(video_on_air())

        run_checks(dog, clock, [channel({50: playing()})] + [channel({})] * 6)

        assert dog.restart.is_set()

    def test_a_short_gap_is_not_enough(self, now):
        dog, clock = self.make(video_on_air())

        run_checks(dog, clock, [channel({})] * 4 + [channel({50: playing()})] + [channel({})] * 4)

        assert not dog.restart.is_set()

    def test_a_clip_that_ran_to_its_end_may_leave_the_layer(self, now):
        dog, clock = self.make(video_on_air())

        run_checks(dog, clock, [channel({50: playing(position=1799.0)})] + [channel({})] * 10)

        assert not dog.restart.is_set()

    def test_leaves_the_start_of_a_slot_alone(self, now):
        now["t"] = START + timedelta(seconds=5)
        dog, clock = self.make(video_on_air())

        run_checks(dog, clock, [channel({})] * 10)

        assert not dog.restart.is_set()

    def test_leaves_the_end_of_a_slot_alone(self, now):
        now["t"] = START + timedelta(minutes=30) - timedelta(seconds=5)
        dog, clock = self.make(video_on_air())

        run_checks(dog, clock, [channel({})] * 10)

        assert not dog.restart.is_set()

    def test_ignores_a_video_that_is_not_on_air(self, now):
        # Not cued yet, or showing the "unavailable" notice instead.
        item = video_on_air()
        item.on_air = False
        dog, clock = self.make(item)

        run_checks(dog, clock, [channel({})] * 10)

        assert not dog.restart.is_set()

    def test_nothing_on_air_means_nothing_to_check(self, now):
        dog, clock = self.make()

        run_checks(dog, clock, [channel({})] * 10)

        assert not dog.restart.is_set()

    def test_the_wrong_file_is_only_reported(self, now, caplog):
        dog, clock = self.make(video_on_air())

        run_checks(dog, clock, [channel({50: playing(path="/mnt/media/other.mxf")})] * 10)

        assert not dog.restart.is_set()

    def test_a_frozen_clock_is_only_reported(self, now):
        dog, clock = self.make(video_on_air())

        run_checks(dog, clock, [channel({50: playing(position=60.0)})] * 10)

        assert not dog.restart.is_set()

    def test_restarts_at_most_once_per_spacing_across_restarts(self, now, monkeypatch):
        # The time of the last restart survives the re-exec in the environment.
        monkeypatch.setattr(watchdog.time, "time", lambda: 10_000.0)
        monkeypatch.setenv(watchdog.LAST_RESTART_ENV, str(10_000.0 - 60))
        dog, clock = self.make(video_on_air())

        run_checks(dog, clock, [channel({})] * 10)

        assert not dog.restart.is_set()

    def test_records_its_restart_for_the_next_process(self, now, monkeypatch):
        monkeypatch.setattr(watchdog.time, "time", lambda: 10_000.0)
        dog, clock = self.make(video_on_air())

        run_checks(dog, clock, [channel({})] * 10)

        assert dog.restart.is_set()
        assert float(watchdog.os.environ[watchdog.LAST_RESTART_ENV]) == 10_000.0


class FakePlayer:
    def __init__(self, answers):
        self.answers = list(answers)

    async def issue(self, cmd, quiet=False):
        answer = self.answers.pop(0) if self.answers else CasparConnectionLost("gone")
        if isinstance(answer, BaseException):
            raise answer
        return answer


class TestRun:
    async def test_never_acts_on_answers_it_cannot_read(self, now, monkeypatch):
        monkeypatch.setattr(watchdog, "CHECK_INTERVAL", 0)
        player = FakePlayer([ValueError("CasparCG command failed: 500")] * 3 + ["garbage"] * 10)
        dog = AirWatchdog(FakeScheduler(video_on_air()), player, clock=Clock())

        await asyncio.wait_for(dog.run(), 1.0)  # returns when the connection goes

        assert not dog.restart.is_set()

    async def test_stops_when_the_connection_goes(self, now, monkeypatch):
        monkeypatch.setattr(watchdog, "CHECK_INTERVAL", 0)
        dog = AirWatchdog(FakeScheduler(), FakePlayer([]), clock=Clock())

        await asyncio.wait_for(dog.run(), 1.0)


# Captured from caspar-sw1 (CasparCG 2.5.0) on 2026-11-14 with a video on
# 1-50, 22 s into its slot.
CAPTURED = (
    '<?xml version="1.0" encoding="utf-8"?>\r\n<channel><stage><layer>'
    "<layer_50><background><producer>empty</producer></background>\n"
    "<foreground><file>\n<clip>0</clip><clip>1433</clip>\n"
    "<name>628124/original/(3) Nytt lys � kollaps.mp4</name>\n"
    "<path>/mnt/media/628124/original/(3) Nytt lys � kollaps.mp4</path>\n"
    "<streams><file><streams_0><fps>25</fps><fps>1</fps></streams_0><streams_1><fps>0</fps>"
    "<fps>0</fps></streams_1></file></streams>\n"
    "<time>22.219999999999999</time><time>1433</time>\n"
    "</file><loop>false</loop><paused>false</paused><producer>ffmpeg</producer></foreground>"
    "</layer_50>"
    "<layer_601><background><producer>empty</producer></background><foreground><file><path>"
    "https://staging.frikanalen.tv/graphics/?duration=9444502</path></file>"
    "<paused>false</paused><producer>html</producer></foreground></layer_601>"
    "</layer></stage></channel>\n\r\n"
)


def test_reads_the_state_caspar_2_5_sends():
    fg = read_foreground(CAPTURED, "1-50")

    assert (fg.producer, fg.time, fg.duration, fg.paused) == ("ffmpeg", 22.22, 1433.0, False)
    assert watchdog.same_file("628124/original/(3) Nytt lys � kollaps.mp4", fg.path)


def test_a_cleared_layer_can_be_an_empty_element():
    # What CasparCG 2.5 reports for a layer right after CLEAR or STOP.
    assert (
        read_foreground(channel({}).replace("<layer>", "<layer><layer_50></layer_50>"), "1-50")
        is None
    )
