"""Clearing layers a previous playout left on air."""

import asyncio
from datetime import timedelta

import pytest

from playout_lib import live
from playout_lib.items import Graphic, localtime
from playout_lib.scheduler import Scheduler, item_key
from playout_lib.stale_layers import OWNED_LAYERS, busy_layers, clear_stale_layers
from playout_lib.video import PrerecordedVideo

STREAM_ID = "6f1c2d6e-8a1b-4c3d-9e2f-0a1b2c3d4e5f"


def channel(producers):
    """INFO 1 as CasparCG 2.5 sends it, for {layer number: producer}."""
    xml = "".join(
        f"<layer_{n}><background><producer>empty</producer></background>"
        f"<foreground><producer>{p}</producer><paused>false</paused></foreground></layer_{n}>"
        for n, p in producers.items()
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f"<channel><framerate>50</framerate><stage><layer>{xml}</layer></stage></channel>\n"
    )


# What caspar1 held on 2026-11-17 after playout restarted at the end of a live
# slot: the bug, the old slot's filler and SRT source, and the new gap graphic.
AFTER_LIVE = channel(
    {100: "image", 50: "ffmpeg", 55: "ffmpeg", 601: "html", 602: "ffmpeg", 60: "empty"}
)


class FakeCaspar:
    def __init__(self, info):
        self.info = info
        self.commands = []

    async def issue(self, command, log_as=None, quiet=False):
        self.commands.append(command)
        if command == "INFO 1":
            return self.info
        return None


def at(minutes=0.0):
    return localtime() + timedelta(minutes=minutes)


async def on_air(*items):
    """A scheduler whose tasks are playing items, without running them."""
    sched = Scheduler()
    for item in items:
        sched.tasks[item_key(item)] = (item, asyncio.create_task(asyncio.Event().wait()))
    return sched


def cancel(sched):
    for _, task in sched.tasks.values():
        task.cancel()


def test_busy_layers_reads_every_layer_with_a_foreground():
    assert busy_layers(AFTER_LIVE) == {"1-100", "1-50", "1-55", "1-601", "1-602"}


def test_busy_layers_refuses_an_answer_that_is_not_a_channel():
    with pytest.raises(ValueError):
        busy_layers(None)
    with pytest.raises(ValueError):
        busy_layers("<channel></channel>")


def test_the_channel_bug_is_not_playout_owned_but_its_layers_are():
    assert "1-100" not in OWNED_LAYERS
    assert {"1-50", "1-55", "1-60", "1-601", "1-602", "1-58", "1-581", "1-52"} <= OWNED_LAYERS


async def test_a_left_over_live_slot_is_cleared_under_a_new_graphic():
    gap = Graphic("https://example.test/graphics/?duration=1000", "1-60", at(-7), at(40))
    sched = await on_air(gap)
    caspar = FakeCaspar(AFTER_LIVE)

    cleared = await sched.clear_stale_layers(caspar)

    assert cleared == ["1-50", "1-55"]
    assert caspar.commands == [
        "INFO 1",
        "CLEAR 1-50",
        "MIXER 1-50 CLEAR",
        "CLEAR 1-55",
        "MIXER 1-55 CLEAR",
    ]
    cancel(sched)


async def test_the_live_slot_still_on_air_is_left_alone():
    slot = live.LiveTransmission(STREAM_ID, "1-50", at(-30), at(30))
    sched = await on_air(slot)
    caspar = FakeCaspar(channel({100: "image", 50: "ffmpeg", 55: "ffmpeg"}))

    assert await sched.clear_stale_layers(caspar) == []
    assert caspar.commands == ["INFO 1"]
    cancel(sched)


async def test_a_live_slot_about_to_start_keeps_its_hidden_source():
    gap = Graphic("https://example.test/graphics/?duration=1000", "1-60", at(-10), at(0.25))
    slot = live.LiveTransmission(STREAM_ID, "1-50", at(0.25), at(60))
    sched = await on_air(gap, slot)
    caspar = FakeCaspar(channel({55: "ffmpeg", 601: "html", 602: "ffmpeg"}))

    assert await sched.clear_stale_layers(caspar) == []
    cancel(sched)


async def test_a_video_keeps_its_layer_and_a_stale_notice_goes():
    video = PrerecordedVideo(1, "1-50", 25000, at(-5), at(20))
    later = Graphic("https://example.test/graphics/?duration=1000", "1-60", at(20), at(30))
    sched = await on_air(video, later)
    caspar = FakeCaspar(channel({50: "ffmpeg", 581: "html", 601: "html", 100: "image"}))

    # The notice belongs to the video's slot; the graphic isn't on yet.
    assert await sched.clear_stale_layers(caspar) == ["1-601"]
    cancel(sched)


async def test_nothing_is_cleared_when_caspar_cannot_be_read():
    sched = await on_air()
    caspar = FakeCaspar("garbage")
    assert await sched.clear_stale_layers(caspar) == []
    assert caspar.commands == ["INFO 1"]


async def test_clear_stale_layers_logs_nothing_to_do(caplog):
    caspar = FakeCaspar(channel({100: "image"}))
    assert await clear_stale_layers(caspar, set()) == []
