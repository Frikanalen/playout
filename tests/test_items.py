from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from playout_lib import items

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

    def test_repr_includes_time_range_and_duration(self):
        graphic = items.Graphic("url", "1-60", NOW, NOW + timedelta(seconds=30))

        assert "30.0s" in repr(graphic)
