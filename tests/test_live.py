from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from playout_lib import items, live

TZ = ZoneInfo("Europe/Oslo")
NOW = datetime(2026, 10, 31, 20, 0, tzinfo=TZ)
STREAM_ID = "6f1c2d6e-8a1b-4c3d-9e2f-0a1b2c3d4e5f"
CONNECT_TIME = 4.0
KEY_ID = "0d9e8f7a-6b5c-4d3e-8f1a-2b3c4d5e6f70"


class Clock:
    """Wall clock for the tests; sleeping is what moves it forward."""

    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += timedelta(seconds=max(0.0, seconds))


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(items, "localtime", clock)
    monkeypatch.setattr(live.asyncio, "sleep", clock.sleep)
    monkeypatch.setattr(items.asyncio, "sleep", clock.sleep)
    return clock


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(live, "LIVE_INPUT_URL", "rtsp://192.0.2.10:8554/")
    monkeypatch.setattr(live, "LIVE_READER_CREDENTIAL", f"{KEY_ID}:s3cr/t")


def info_xml(layers):
    """INFO as CasparCG 2.5 returns it: the whole channel, whatever layer was asked."""
    xml = ""
    for number, (producer, position) in layers.items():
        if producer == "ffmpeg":
            foreground = (
                f"<file><time>{position}</time><time>0</time></file><producer>ffmpeg</producer>"
            )
        else:
            # A source still connecting, or a dead one, never gets past this.
            foreground = (
                "<file><time>0</time><time>0</time></file><producer>transition</producer>"
                "<transition><producer>ffmpeg</producer><type>cut</type></transition>"
            )
        xml += f"<layer_{number}><foreground>{foreground}</foreground></layer_{number}>"
    header = '<?xml version="1.0" encoding="utf-8"?>\r\n'
    return f"{header}<channel><stage><layer>{xml}</layer></stage></channel>\r\n"


@pytest.fixture
def caspar(monkeypatch, clock):
    """A CasparCG whose live source is up unless `dead_bring_ups` says otherwise."""
    from playout_lib import caspar_player

    class FakeCaspar:
        def __init__(self):
            self.commands = []
            self.sent_at = []
            self.logged = []
            self.dead_bring_ups = 0
            # Freeze the source after this many seconds on air (None: never).
            self.stall_after = None
            self.layers = {}
            self.opacity = {}
            # Seconds after NOW during which the encoder is not publishing.
            self.outages = []

        def publishing(self):
            seconds = (clock.now - NOW).total_seconds()
            return not any(start <= seconds < end for start, end in self.outages)

        def reading(self):
            """Bytes read by each live layer that MediaMTX still feeds.

            A drop ends the reader for good: CasparCG never reconnects, though
            its clock in INFO runs on.
            """
            readers = {}
            for kind, started in self.layers.values():
                if kind == "live" and self._fed(started):
                    since = (started - NOW).total_seconds()
                    readers[f"session-{since}"] = (clock.now - started).total_seconds() * 1e5
            return readers

        def _fed(self, started):
            since = (started - NOW).total_seconds()
            now = (clock.now - NOW).total_seconds()
            return not any(start < now and end > since for start, end in self.outages)

        def _live(self, started):
            # CasparCG takes about 4 seconds to connect to an RTSP source and
            # shows a transition producer until then.
            seconds = (clock.now - started).total_seconds() - CONNECT_TIME
            if seconds < 0:
                return ("transition", 0)
            if self.stall_after is not None:
                seconds = min(seconds, self.stall_after)
            return ("ffmpeg", seconds)

        async def issue(self, cmd, log_as=None):
            self.commands.append(cmd)
            self.sent_at.append((clock.now - NOW).total_seconds())
            self.logged.append(log_as or cmd)
            words = cmd.split()
            layer = words[1].split("-")[1] if len(words) > 1 and "-" in words[1] else None
            if words[0] == "PLAY" and "rtsp://" in cmd:
                if self.dead_bring_ups or not self.publishing():
                    self.dead_bring_ups -= 1
                    self.layers[layer] = ("dead", None)
                else:
                    self.layers[layer] = ("live", clock.now)
            elif words[0] == "PLAY":
                self.layers[layer] = ("filler", None)
            elif words[0] in ("CLEAR", "STOP"):
                self.layers.pop(layer, None)
            elif words[0] == "MIXER" and words[2] == "OPACITY":
                self.opacity[layer] = float(words[3])
            elif words[0] == "MIXER" and words[2] == "CLEAR":
                self.opacity.pop(layer, None)
            elif words[0] == "INFO":
                shown = {}
                for number, (kind, started) in self.layers.items():
                    if kind == "live":
                        shown[number] = self._live(started)
                    elif kind == "filler":
                        shown[number] = ("ffmpeg", (clock.now - NOW).total_seconds())
                    else:
                        shown[number] = ("transition", 0)
                return info_xml(shown)

        def on_air(self):
            """What program out shows: the live layer when visible, else the programme."""
            if "55" in self.layers and self.opacity.get("55", 1.0) > 0:
                kind, started = self.layers["55"]
                if kind != "live":
                    return "black"
                if not self._fed(started) or self._live(started)[0] != "ffmpeg":
                    return "frozen"
                return "live"
            return self.layers.get("50", (None,))[0]

    fake = FakeCaspar()
    monkeypatch.setattr(caspar_player.current_player, "issue", fake.issue)
    return fake


@pytest.fixture
def mediamtx(monkeypatch, caspar):
    """MediaMTX metrics that follow the fake CasparCG and its encoder."""
    monkeypatch.setattr(live, "LIVE_METRICS_URL", "http://mediamtx:9998/metrics")

    async def read_path_state(path):
        assert path == f"contrib/live/{STREAM_ID}"
        return live.PathState(ready=caspar.publishing(), readers=caspar.reading())

    monkeypatch.setattr(live, "read_path_state", read_path_state)
    return caspar


def make_live(minutes=30, start=NOW):
    return live.LiveTransmission(STREAM_ID, "1-50", start, start + timedelta(minutes=minutes))


async def scheduled(item):
    """Run item as the scheduler does: prepare ahead, then cue at the start time."""
    await item.sleep_until_time_to_prepare()
    await item.prepare()
    await item.sleep_until_time_to_play()
    await item.cue()


@pytest.fixture
def program_out(caspar, clock, monkeypatch):
    """What program out showed after each sleep, by seconds after NOW."""
    seen = {}
    sleep = live.asyncio.sleep

    async def watching_sleep(seconds):
        await sleep(seconds)
        seen[(clock.now - NOW).total_seconds()] = caspar.on_air()

    monkeypatch.setattr(live.asyncio, "sleep", watching_sleep)
    monkeypatch.setattr(items.asyncio, "sleep", watching_sleep)
    return seen


class TestUrl:
    def test_reads_the_contribution_path_with_its_credential(self, configured):
        assert make_live()._url() == (
            f"rtsp://{KEY_ID}:s3cr%2Ft@192.0.2.10:8554/contrib/live/{STREAM_ID}"
        )

    def test_redacts_the_password(self, configured):
        assert "s3cr" not in make_live()._url(redact=True)

    def test_reads_without_credential_when_none_is_configured(self, configured, monkeypatch):
        monkeypatch.setattr(live, "LIVE_READER_CREDENTIAL", "")

        assert make_live()._url() == f"rtsp://192.0.2.10:8554/contrib/live/{STREAM_ID}"

    def test_is_none_without_an_input_url(self, monkeypatch):
        monkeypatch.setattr(live, "LIVE_INPUT_URL", "")

        assert make_live()._url() is None


class TestForegroundTime:
    def test_reads_the_position_of_the_asked_layer(self):
        info = info_xml({"50": ("ffmpeg", 1041.44), "90": ("ffmpeg", 4.18)})
        assert live.foreground_time(info, "1-90") == 4.18
        assert live.foreground_time(info, "1-50") == 1041.44

    def test_a_connecting_or_dead_source_has_no_position(self):
        assert live.foreground_time(info_xml({"90": ("transition", 0)}), "1-90") is None

    def test_an_empty_layer_or_garbage_has_no_position(self):
        assert live.foreground_time(info_xml({"50": ("ffmpeg", 1.0)}), "1-90") is None
        assert live.foreground_time("not xml", "1-90") is None
        assert live.foreground_time(None, "1-90") is None


LIVE = f'path="contrib/live/{STREAM_ID}"'
METRICS = f"""# HELP paths
paths{{name="contrib/live/{STREAM_ID}",state="ready"}} 1
paths{{name="contrib/live/other",state="ready"}} 1
rtsp_sessions{{id="a1",{LIVE},remoteAddr="192.0.2.101:51000",state="read"}} 1
rtsp_sessions_outbound_bytes{{id="a1",{LIVE},remoteAddr="192.0.2.101:51000",state="read"}} 123456
rtsp_sessions_outbound_bytes{{id="b2",path="contrib/live/other",state="read"}} 999
srt_conns{{id="c3",{LIVE},state="publish"}} 1
"""


class TestPathState:
    def test_reads_publisher_and_readers_of_the_path(self):
        state = live.path_state(METRICS, f"contrib/live/{STREAM_ID}")

        assert state.ready
        assert state.readers == {"a1": 123456.0}

    def test_an_unknown_path_is_not_ready(self):
        assert live.path_state(METRICS, "contrib/live/gone") == live.PathState()

    def test_flowing_needs_a_reader_whose_bytes_grow(self):
        before = live.PathState(True, {"a1": 100.0})

        assert live.still_flowing(before, live.PathState(True, {"a1": 200.0}))
        assert not live.still_flowing(before, live.PathState(True, {"a1": 100.0}))
        assert not live.still_flowing(before, live.PathState(False, {}))
        assert live.still_flowing(None, live.PathState(True, {"a1": 1.0}))


class TestCue:
    async def test_starts_hidden_ahead_and_shows_live_at_the_start_time(
        self, configured, caspar, program_out
    ):
        item = make_live(minutes=1, start=NOW + timedelta(seconds=30))

        await scheduled(item)

        play = next(i for i, c in enumerate(caspar.commands) if "rtsp://" in c)
        assert caspar.commands[play].startswith(f'PLAY 1-55 "rtsp://{KEY_ID}:')
        assert caspar.commands[play - 2 : play] == ["MIXER 1-55 OPACITY 0", "MIXER 1-55 VOLUME 0"]
        # Started 15 s ahead, and nothing touched the programme layer before the slot.
        assert not any(c.endswith(" 1-50") or " 1-50 " in c for c in caspar.commands[:play])
        assert all(kind is None for t, kind in program_out.items() if t < 30)
        # On air right at the start time.
        assert caspar.sent_at[caspar.commands.index("MIXER 1-55 OPACITY 1")] == 30.0
        assert program_out[32.0] == "live"
        assert caspar.commands[-4:] == [
            "CLEAR 1-55",
            "MIXER 1-55 CLEAR",
            "MIXER 1-50 VOLUME 1.0000",
            "STOP 1-50",
        ]

    async def test_mutes_the_filler_under_live(self, configured, caspar):
        await make_live(minutes=1).cue()

        show = caspar.commands.index("MIXER 1-55 OPACITY 1")
        assert caspar.commands[show - 2 : show] == [
            "MIXER 1-50 VOLUME 0",
            "MIXER 1-55 VOLUME 1.0000",
        ]

    async def test_the_bug_says_direkte_only_while_live_is_on_air(self, configured, caspar):
        caspar.stall_after = 30

        await make_live(minutes=2).cue()

        bugs = [c for c in caspar.commands if c.startswith("PLAY 1-100 ")]
        show = caspar.commands.index("MIXER 1-55 OPACITY 1")
        assert caspar.commands[show + 1] == "PLAY 1-100 stills/screenbug_live"
        # Back to the plain bug with the filler after the stall, and at the end.
        hide = caspar.commands.index("MIXER 1-55 OPACITY 0", show)
        assert "PLAY 1-100 stills/screenbug" in caspar.commands[hide : hide + 3]
        assert bugs[-1] == "PLAY 1-100 stills/screenbug"

    async def test_never_shows_black(self, configured, caspar, program_out):
        caspar.dead_bring_ups = 2

        await make_live(minutes=2).cue()

        assert "live" in program_out.values()
        assert set(program_out.values()) <= {"filler", "live", None}

    async def test_never_logs_the_password(self, configured, caspar):
        await scheduled(make_live(minutes=1, start=NOW + timedelta(seconds=30)))

        assert not any("s3cr" in line for line in caspar.logged)

    async def test_a_dead_source_never_reaches_air(self, configured, caspar, program_out):
        caspar.dead_bring_ups = 1000

        await make_live(minutes=2).cue()

        assert "MIXER 1-55 OPACITY 1" not in caspar.commands
        assert set(program_out.values()) <= {"filler", None}
        # It kept trying for the whole slot.
        assert len([c for c in caspar.commands if "rtsp://" in c]) > 3
        assert caspar.commands[-1] == "STOP 1-50"

    async def test_a_late_encoder_is_taken_once_it_flows(self, configured, caspar):
        caspar.dead_bring_ups = 2

        await make_live(minutes=2).cue()

        assert len([c for c in caspar.commands if "rtsp://" in c]) == 3
        assert caspar.commands.count("MIXER 1-55 OPACITY 1") == 1

    async def test_without_metrics_a_frozen_clock_goes_back_to_filler(self, configured, caspar):
        caspar.stall_after = 30

        await make_live(minutes=2).cue()

        hide = caspar.commands.index(
            "MIXER 1-55 OPACITY 0", caspar.commands.index("MIXER 1-55 OPACITY 1")
        )
        assert any("rtsp://" in c for c in caspar.commands[hide:])

    async def test_an_encoder_drop_goes_to_filler_and_comes_back(
        self, configured, mediamtx, program_out
    ):
        mediamtx.outages = [(30, 50)]

        await make_live(minutes=2).cue()

        # Filler within a few seconds of the drop, CasparCG's clock notwithstanding.
        assert any(30 < t <= 36 and kind == "filler" for t, kind in program_out.items())
        # Back on air shortly after the encoder's return.
        assert any(50 < t <= 60 and kind == "live" for t, kind in program_out.items())
        assert mediamtx.commands.count("MIXER 1-55 OPACITY 1") == 2
        # The filler ran underneath throughout: it was played once.
        assert mediamtx.commands.count("PLAY 1-50 filler/FrikanalenLoop loop 0") == 1
        # Never a dead picture for longer than the drop takes to notice.
        frozen = [t for t, kind in program_out.items() if kind == "frozen"]
        assert all(30 < t <= 35 for t in frozen)

    async def test_a_steady_source_stays_on_air(self, configured, mediamtx):
        await make_live(minutes=2).cue()

        assert mediamtx.commands.count("MIXER 1-55 OPACITY 1") == 1
        assert len([c for c in mediamtx.commands if "rtsp://" in c]) == 1

    async def test_an_unreachable_metrics_endpoint_keeps_the_source_on_air(
        self, configured, mediamtx, monkeypatch
    ):
        async def unreachable(path):
            return None

        monkeypatch.setattr(live, "read_path_state", unreachable)

        await make_live(minutes=2).cue()

        assert mediamtx.commands.count("MIXER 1-55 OPACITY 1") == 1

    async def test_an_error_covers_the_rest_of_the_slot_with_filler(
        self, configured, caspar, monkeypatch
    ):
        async def broken(layer):
            raise TimeoutError

        monkeypatch.setattr(live.LiveTransmission, "_position", lambda self, layer: broken(layer))

        await make_live(minutes=1).cue()

        assert "MIXER 1-55 OPACITY 1" not in caspar.commands
        assert caspar.commands[-1] == "STOP 1-50"
        assert "CLEAR 1-55" in caspar.commands

    async def test_plays_filler_when_live_input_is_unconfigured(self, monkeypatch, caspar):
        monkeypatch.setattr(live, "LIVE_INPUT_URL", "")

        await make_live(minutes=1).cue()

        assert "PLAY 1-50 filler/FrikanalenLoop loop 0" in caspar.commands
        assert not any("rtsp://" in c for c in caspar.commands)
