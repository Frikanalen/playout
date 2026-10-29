from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from playout_lib import items, live

TZ = ZoneInfo("Europe/Oslo")
NOW = datetime(2026, 10, 31, 20, 0, tzinfo=TZ)
STREAM_ID = "6f1c2d6e-8a1b-4c3d-9e2f-0a1b2c3d4e5f"
KEY_ID = "0d9e8f7a-6b5c-4d3e-8f1a-2b3c4d5e6f70"


@pytest.fixture(autouse=True)
def frozen_time(monkeypatch):
    monkeypatch.setattr(items, "localtime", lambda: NOW)

    async def no_sleep(seconds):
        return None

    monkeypatch.setattr(live.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(items.asyncio, "sleep", no_sleep)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(live, "LIVE_INPUT_URL", "rtsp://192.0.2.10:8554/")
    monkeypatch.setattr(live, "LIVE_SOURCE_CREDENTIALS", {STREAM_ID: f"{KEY_ID}:s3cr/t"})


@pytest.fixture
def caspar(monkeypatch):
    """Record AMCP commands; PLAYs of the live URL fail while `refusals` > 0."""
    from playout_lib import caspar_player

    class FakeCaspar:
        def __init__(self):
            self.commands = []
            self.logged = []
            self.refusals = 0

        async def issue(self, cmd, log_as=None):
            self.commands.append(cmd)
            self.logged.append(log_as or cmd)
            if "rtsp://" in cmd and self.refusals:
                self.refusals -= 1
                raise ValueError("CasparCG command failed: 404 PLAY FAILED")

    fake = FakeCaspar()
    monkeypatch.setattr(caspar_player.current_player, "issue", fake.issue)
    return fake


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
        monkeypatch.setattr(live, "LIVE_SOURCE_CREDENTIALS", {})

        assert make_live()._url() == f"rtsp://192.0.2.10:8554/contrib/live/{STREAM_ID}"

    def test_is_none_without_an_input_url(self, monkeypatch):
        monkeypatch.setattr(live, "LIVE_INPUT_URL", "")

        assert make_live()._url() is None


class TestCue:
    async def test_plays_the_source_at_unity_gain_and_stops_at_the_end(self, configured, caspar):
        await make_live().cue()

        assert caspar.commands[0] == "MIXER 1-50 VOLUME 1.0000"
        assert caspar.commands[1].startswith(f'PLAY 1-50 "rtsp://{KEY_ID}:')
        assert caspar.commands[-1] == "STOP 1-50"

    async def test_never_logs_the_password(self, configured, caspar):
        await make_live().cue()

        assert not any("s3cr" in line for line in caspar.logged)

    async def test_covers_with_filler_until_the_source_comes_up(self, configured, caspar):
        caspar.refusals = 2

        await make_live().cue()

        plays = [c for c in caspar.commands if c.startswith("PLAY")]
        assert plays[0].startswith('PLAY 1-50 "rtsp://')
        assert plays[1] == "PLAY 1-50 filler/FrikanalenLoop loop 0"
        assert plays[4].startswith('PLAY 1-50 "rtsp://')
        assert len(plays) == 5

    async def test_gives_up_retrying_near_the_end_of_the_slot(self, configured, caspar):
        caspar.refusals = 1000

        await live.LiveTransmission(STREAM_ID, "1-50", NOW, NOW + timedelta(seconds=5)).cue()

        assert caspar.commands[-2] == "PLAY 1-50 filler/FrikanalenLoop loop 0"
        assert caspar.commands[-1] == "STOP 1-50"

    async def test_plays_filler_when_live_input_is_unconfigured(self, monkeypatch, caspar):
        monkeypatch.setattr(live, "LIVE_INPUT_URL", "")

        await make_live().cue()

        assert "PLAY 1-50 filler/FrikanalenLoop loop 0" in caspar.commands
        assert not any("rtsp://" in c for c in caspar.commands)
