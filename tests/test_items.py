from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from playout_lib import caspar_player, items

TZ = ZoneInfo("Europe/Oslo")
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=TZ)


@pytest.fixture(autouse=True)
def frozen_localtime(monkeypatch):
    monkeypatch.setattr(items, "localtime", lambda: NOW)


class TestPlannedItemTiming:
    def test_already_done_is_false_before_end_time(self):
        item = items.PlannedItem("1-50", NOW - timedelta(minutes=5), NOW + timedelta(minutes=5))

        assert item.already_done() is False

    def test_already_done_is_true_after_end_time(self):
        item = items.PlannedItem("1-50", NOW - timedelta(hours=2), NOW - timedelta(hours=1))

        assert item.already_done() is True

    def test_seconds_left_reflects_remaining_time(self):
        item = items.PlannedItem("1-50", NOW, NOW + timedelta(seconds=90))

        assert item._seconds_left() == pytest.approx(90)


class TestGraphic:
    def test_construction_does_not_touch_network(self):
        graphic = items.Graphic(
            "https://example.com/graphics/?duration=5000", "1-60", NOW, NOW + timedelta(seconds=5)
        )

        assert graphic.url == "https://example.com/graphics/?duration=5000"
        assert graphic.has_been_prepared is False

    def test_a_graphic_cued_on_time_asks_for_its_whole_gap(self):
        graphic = items.Graphic(
            "https://example.com/graphics/?duration=60000",
            "1-60",
            NOW + timedelta(seconds=5),
            NOW + timedelta(seconds=65),
        )

        assert graphic.timed_url() == "https://example.com/graphics/?duration=60000"

    def test_a_graphic_cued_late_asks_for_what_is_left(self):
        graphic = items.Graphic(
            "https://example.com/graphics/?duration=7200000&unavailable=Ukeslutt",
            "1-60",
            NOW - timedelta(hours=1, minutes=30),
            NOW + timedelta(minutes=30),
        )

        assert graphic.timed_url() == (
            "https://example.com/graphics/?duration=1800000&unavailable=Ukeslutt"
        )

    def test_a_url_without_a_duration_is_left_alone(self):
        graphic = items.Graphic("https://example.com/x/", "1-60", NOW, NOW + timedelta(seconds=30))

        assert graphic.timed_url() == "https://example.com/x/"

    def test_repr_includes_time_range_and_duration(self):
        graphic = items.Graphic("url", "1-60", NOW, NOW + timedelta(seconds=30))

        assert "30.0s" in repr(graphic)

    @staticmethod
    def _record(monkeypatch, fail_on=()):
        issued = []

        # The clock is frozen, so let every graphic end as soon as it waits.
        async def ends_now(self, margin=0.0):
            pass

        monkeypatch.setattr(items.PlannedItem, "_wait_until_end", ends_now)

        async def fake_issue(cmd):
            issued.append(cmd)
            if any(cmd.startswith(prefix) for prefix in fail_on):
                raise ValueError("CasparCG command failed: 404 PLAY FAILED")

        monkeypatch.setattr(caspar_player.current_player, "issue", fake_issue)
        return issued

    async def test_a_prepared_graphic_loops_the_music_and_stops_it_at_the_end(self, monkeypatch):
        issued = self._record(monkeypatch)
        graphic = items.Graphic("url", "1-60", NOW, NOW + timedelta(seconds=3))

        # Item.__init__ shadows prepare() with None, so call it off the class.
        await items.Graphic.prepare(graphic)
        await graphic.cue()

        assert "LOADBG 1-602 filler/deep_relaxation LOOP" in issued
        assert "MIXER 1-60 VOLUME 0" in issued
        assert "MIXER 1-602 VOLUME 1.0000" in issued
        assert issued.index("PLAY 1-602") > issued.index("CG 1-601 PLAY 0")
        assert issued[-2:] == ["CLEAR 1-602", "MIXER 1-602 CLEAR"]

    async def test_a_graphic_cued_unprepared_plays_the_music_by_name(self, monkeypatch):
        issued = self._record(monkeypatch)
        graphic = items.Graphic("url", "1-58", NOW, NOW + timedelta(seconds=3))

        await graphic.cue()

        assert "PLAY 1-582 filler/deep_relaxation LOOP" in issued
        assert "CLEAR 1-582" in issued

    async def test_the_music_fades_out_with_the_graphic(self, monkeypatch):
        issued = self._record(monkeypatch)
        graphic = items.Graphic("url", "1-60", NOW, NOW + timedelta(seconds=10))

        await graphic.cue()

        assert "MIXER 1-602 VOLUME 0 50 easeinsine" in issued

    async def test_missing_music_leaves_the_graphic_on_air(self, monkeypatch):
        issued = self._record(monkeypatch, fail_on=("LOADBG 1-602", "PLAY 1-602"))
        graphic = items.Graphic("url", "1-60", NOW, NOW + timedelta(seconds=3))

        # Item.__init__ shadows prepare() with None, so call it off the class.
        await items.Graphic.prepare(graphic)
        await graphic.cue()

        assert graphic.has_been_prepared is True
        assert "CG 1-601 PLAY 0" in issued
        assert "PLAY 1-602 filler/deep_relaxation LOOP" in issued

    async def test_no_music_configured_plays_the_graphic_silent(self, monkeypatch):
        issued = self._record(monkeypatch)
        monkeypatch.setattr(items, "FILLER_MUSIC", "")
        graphic = items.Graphic("url", "1-60", NOW, NOW + timedelta(seconds=3))

        # Item.__init__ shadows prepare() with None, so call it off the class.
        await items.Graphic.prepare(graphic)
        await graphic.cue()

        assert not any("1-602" in cmd or "VOLUME" in cmd for cmd in issued)


class TestFillerLoop:
    def test_repr_includes_time_range_and_duration(self):
        filler = items.FillerLoop("1-60", NOW, NOW + timedelta(seconds=20))

        assert "20.0s" in repr(filler)
        assert "FillerLoop" in repr(filler)

    async def test_cue_plays_and_clears_the_filler_reel(self, monkeypatch):
        issued = []

        async def fake_issue(cmd):
            issued.append(cmd)

        monkeypatch.setattr(caspar_player.current_player, "issue", fake_issue)

        filler = items.FillerLoop("1-60", NOW, NOW)  # zero-length: no waiting needed
        await filler.cue()

        assert issued[0] == "PLAY 1-60 filler/FrikanalenLoop loop 0"
        assert issued[-1] == "CLEAR 1-60"
