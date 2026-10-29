from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from playout_lib import items, live

TZ = ZoneInfo("Europe/Oslo")
NOW = datetime(2026, 10, 31, 20, 0, tzinfo=TZ)
STREAM_ID = "6f1c2d6e-8a1b-4c3d-9e2f-0a1b2c3d4e5f"
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
            self.logged = []
            self.dead_bring_ups = 0
            # Freeze the source after this many seconds on air (None: never).
            self.stall_after = None
            self.layers = {}
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
                if kind != "live":
                    continue
                since = (started - NOW).total_seconds()
                now = (clock.now - NOW).total_seconds()
                if any(start < now and end > since for start, end in self.outages):
                    continue
                readers[f"session-{since}"] = (clock.now - started).total_seconds() * 1e5
            return readers

        def _live(self, started):
            seconds = (clock.now - started).total_seconds()
            if self.stall_after is not None:
                seconds = min(seconds, self.stall_after)
            return ("ffmpeg", seconds)

        async def issue(self, cmd, log_as=None):
            self.commands.append(cmd)
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
            elif words[0] == "SWAP":
                other = words[2].split("-")[1]
                a, b = self.layers.pop(layer, None), self.layers.pop(other, None)
                if a:
                    self.layers[other] = a
                if b:
                    self.layers[layer] = b
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


def make_live(minutes=30):
    return live.LiveTransmission(STREAM_ID, "1-50", NOW, NOW + timedelta(minutes=minutes))


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
    async def test_probes_hidden_then_cuts_to_air_and_stops_at_the_end(self, configured, caspar):
        await make_live(minutes=1).cue()

        assert caspar.commands[0] == "MIXER 1-50 VOLUME 1.0000"
        assert caspar.commands[1] == "PLAY 1-50 filler/FrikanalenLoop loop 0"
        assert "MIXER 1-49 VOLUME 0" in caspar.commands
        live_plays = [c for c in caspar.commands if "rtsp://" in c]
        assert len(live_plays) == 1
        assert live_plays[0].startswith(f'PLAY 1-49 "rtsp://{KEY_ID}:')
        assert "SWAP 1-49 1-50" in caspar.commands
        assert caspar.commands[-1] == "STOP 1-50"

    async def test_is_on_air_during_the_slot(self, configured, caspar, clock, monkeypatch):
        seen = []

        async def watching_sleep(seconds):
            await clock.sleep(seconds)
            seen.append(caspar.on_air())

        monkeypatch.setattr(live.asyncio, "sleep", watching_sleep)
        await make_live(minutes=1).cue()

        assert "live" in seen
        # Never black: layer 50 only ever carries filler or a flowing source.
        assert set(seen) <= {"filler", "live", None}

    async def test_never_logs_the_password(self, configured, caspar):
        await make_live(minutes=1).cue()

        assert not any("s3cr" in line for line in caspar.logged)

    async def test_a_dead_source_never_reaches_air(self, configured, caspar):
        caspar.dead_bring_ups = 1000

        await make_live(minutes=2).cue()

        assert not any(c.startswith("SWAP") for c in caspar.commands)
        assert not any(c.startswith('PLAY 1-50 "rtsp://') for c in caspar.commands)
        # It kept trying for the whole slot, on the hidden layer only.
        assert len([c for c in caspar.commands if "rtsp://" in c]) > 3
        assert caspar.commands[-1] == "STOP 1-50"

    async def test_a_late_encoder_is_taken_once_it_flows(self, configured, caspar):
        caspar.dead_bring_ups = 2

        await make_live(minutes=2).cue()

        assert len([c for c in caspar.commands if "rtsp://" in c]) == 3
        assert caspar.commands.count("SWAP 1-49 1-50") == 1

    async def test_without_metrics_a_frozen_clock_goes_back_to_filler(self, configured, caspar):
        caspar.stall_after = 30

        await make_live(minutes=2).cue()

        filler = "PLAY 1-50 filler/FrikanalenLoop loop 0"
        assert caspar.commands.count(filler) >= 2
        stall = caspar.commands.index(filler, 2)
        assert any("rtsp://" in c for c in caspar.commands[stall:])

    async def test_an_encoder_drop_goes_to_filler_and_comes_back(
        self, configured, mediamtx, clock, monkeypatch
    ):
        mediamtx.outages = [(30, 50)]
        seen = {}

        async def watching_sleep(seconds):
            await clock.sleep(seconds)
            seen[(clock.now - NOW).total_seconds()] = mediamtx.on_air()

        monkeypatch.setattr(live.asyncio, "sleep", watching_sleep)
        await make_live(minutes=2).cue()

        # Filler within a few seconds of the drop, CasparCG's clock notwithstanding.
        assert any(30 < t <= 36 and kind == "filler" for t, kind in seen.items())
        # Back on air within a probe of the encoder's return.
        assert any(50 < t <= 60 and kind == "live" for t, kind in seen.items())
        assert mediamtx.commands.count("SWAP 1-49 1-50") == 2
        # No probes while nothing was publishing.
        probes = [c for c in mediamtx.commands if "rtsp://" in c]
        assert len(probes) == 2

    async def test_a_steady_source_stays_on_air(self, configured, mediamtx):
        await make_live(minutes=2).cue()

        assert mediamtx.commands.count("SWAP 1-49 1-50") == 1
        assert mediamtx.commands.count("PLAY 1-50 filler/FrikanalenLoop loop 0") == 1

    async def test_an_unreachable_metrics_endpoint_keeps_the_source_on_air(
        self, configured, mediamtx, monkeypatch
    ):
        async def unreachable(path):
            return None

        monkeypatch.setattr(live, "read_path_state", unreachable)

        await make_live(minutes=2).cue()

        assert mediamtx.commands.count("SWAP 1-49 1-50") == 1
        assert mediamtx.commands.count("PLAY 1-50 filler/FrikanalenLoop loop 0") == 1

    async def test_plays_filler_when_live_input_is_unconfigured(self, monkeypatch, caspar):
        monkeypatch.setattr(live, "LIVE_INPUT_URL", "")

        await make_live(minutes=1).cue()

        assert "PLAY 1-50 filler/FrikanalenLoop loop 0" in caspar.commands
        assert not any("rtsp://" in c for c in caspar.commands)
