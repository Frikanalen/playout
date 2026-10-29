"""Reconciling the running tasks with a schedule that changed under them."""

import asyncio
from datetime import timedelta

import pytest

from playout_lib import caspar_player, live, scheduler
from playout_lib.items import FillerLoop, Graphic, PlannedItem, localtime
from playout_lib.scheduler import Scheduler, item_key

STREAM_ID = "6f1c2d6e-8a1b-4c3d-9e2f-0a1b2c3d4e5f"


@pytest.fixture(autouse=True)
def commands(monkeypatch):
    """Every AMCP command issued, in order."""
    issued = []

    async def issue(command, log_as=None):
        issued.append(command)
        return "202 OK"

    monkeypatch.setattr(caspar_player.current_player, "issue", issue)
    return issued


class Recorded(PlannedItem):
    """An item that notes when it is cued and when it leaves the air."""

    log: list = []

    def __init__(self, name, start, end, layer="1-50"):
        super().__init__(layer, start, end)
        self.video_id = name

    async def cue(self):
        self.log.append(("cue", self.video_id))
        try:
            await self._completion()
            self.log.append(("ended", self.video_id))
        except asyncio.CancelledError:
            self.log.append(("cancelled", self.video_id))
            raise

    def __repr__(self):
        return f"[Recorded {self.video_id}]"


@pytest.fixture(autouse=True)
def log():
    Recorded.log = []
    return Recorded.log


def at(minutes=0.0):
    return localtime() + timedelta(minutes=minutes)


async def settle():
    for _ in range(5):
        await asyncio.sleep(0)


async def test_an_unchanged_schedule_keeps_its_tasks():
    t = [at(10), at(20), at(30)]
    sched = Scheduler()
    await sched.reconcile([Recorded("a", t[0], t[1]), Recorded("b", t[1], t[2])])
    before = {key: task for key, (_, task) in sched.tasks.items()}

    # A fresh load builds new item objects for the same bookings.
    await sched.reconcile([Recorded("a", t[0], t[1]), Recorded("b", t[1], t[2])])

    assert {key: task for key, (_, task) in sched.tasks.items()} == before
    assert not any(task.done() for task in before.values())
    for task in before.values():
        task.cancel()


async def test_bookings_are_added_moved_and_removed():
    start = at(10)
    sched = Scheduler()
    a, b = Recorded("a", start, start + timedelta(minutes=10)), Recorded("b", at(30), at(40))
    await sched.reconcile([a, b])
    task_a = sched.tasks[item_key(a)][1]

    moved = Recorded("a", start, start + timedelta(minutes=5))
    c = Recorded("c", at(50), at(60))
    await sched.reconcile([moved, c])
    await settle()

    assert task_a.cancelled(), "a future item that changed is replaced"
    assert sched.tasks[item_key(moved)][0] is moved
    assert item_key(b) not in sched.tasks
    assert item_key(c) in sched.tasks
    for _, task in sched.tasks.values():
        task.cancel()


async def test_an_item_on_air_only_has_its_end_moved(log):
    start = at(-1)
    sched = Scheduler()
    on_air = Recorded("a", start, at(10))
    await sched.reconcile([on_air])
    await settle()
    task = sched.tasks[item_key(on_air)][1]
    assert log == [("cue", "a")]

    await sched.reconcile([Recorded("a", start, localtime() + timedelta(seconds=0.05))])
    await asyncio.wait_for(task, 2)

    assert sched.tasks[item_key(on_air)][1] is task, "the running task is kept"
    assert log == [("cue", "a"), ("ended", "a")]


async def test_a_replaced_item_leaves_the_air_before_its_replacement_starts(log):
    start = at(-1)
    sched = Scheduler()
    await sched.reconcile([Recorded("video", start, at(10))])
    await settle()

    await sched.reconcile([Recorded("live", at(-0.5), at(10))])
    await settle()

    assert log == [("cue", "video"), ("cancelled", "video"), ("cue", "live")]
    for _, task in sched.tasks.values():
        task.cancel()


async def test_a_graphic_whose_gap_shrinks_stays_on_air():
    start = at(-1)
    long = Graphic("https://graphics/?duration=3600000", "1-60", start, at(59))
    short = Graphic("https://graphics/?duration=1800000", "1-60", start, at(29))
    assert item_key(long) == item_key(short)


async def test_a_failed_item_is_not_restarted_on_every_load(log):
    class Broken(Recorded):
        async def cue(self):
            self.log.append(("cue", self.video_id))
            raise RuntimeError("boom")

    start, end = at(-1), at(10)
    sched = Scheduler()
    await sched.reconcile([Broken("x", start, end)])
    await settle()
    await sched.reconcile([Broken("x", start, end)])
    await settle()
    assert log.count(("cue", "x")) == 1


async def test_a_live_slot_cancelled_while_preparing_clears_the_live_layer(monkeypatch, commands):
    monkeypatch.setattr(live, "LIVE_INPUT_URL", "rtsp://192.0.2.10:8554/")
    monkeypatch.setattr(live, "LIVE_READER_CREDENTIAL", "key:secret")
    # Within the preroll, so it starts the source and then waits for the slot.
    slot = live.LiveTransmission(STREAM_ID, "1-50", localtime() + timedelta(seconds=10), at(30))
    sched = Scheduler()
    await sched.reconcile([slot])
    for _ in range(50):
        if any(c.startswith("PLAY 1-55") for c in commands):
            break
        await asyncio.sleep(0.01)
    assert any(c.startswith("PLAY 1-55") for c in commands)

    await sched.reconcile([])

    assert commands[-2:] == ["CLEAR 1-55", "MIXER 1-55 CLEAR"]
    assert not sched.tasks


async def test_run_reloads_when_told_and_keeps_playing_through_a_failed_load(monkeypatch):
    monkeypatch.setattr(scheduler, "SETTLE_SECONDS", 0)
    loads = []
    ready = asyncio.Event()

    async def load():
        loads.append(len(loads))
        if len(loads) == 2:
            raise RuntimeError("API down")
        if len(loads) >= 3:
            ready.set()
        return [FillerLoop("1-60", at(10), at(20))]

    async def listen(changed):
        await asyncio.sleep(0.01)
        changed()
        await asyncio.sleep(0.01)
        changed()
        await asyncio.Event().wait()

    sched = Scheduler(load=load, listen=listen)
    runner = asyncio.create_task(sched.run())
    await asyncio.wait_for(ready.wait(), 2)
    runner.cancel()
    assert len(loads) == 3
    assert len(sched.tasks) == 1
    for _, task in sched.tasks.values():
        task.cancel()


def test_the_next_load_comes_at_the_poll_or_just_after_midnight():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    oslo = ZoneInfo("Europe/Oslo")
    assert scheduler.seconds_until_next_load(datetime(2026, 10, 31, 20, 0, tzinfo=oslo)) == 900
    assert scheduler.seconds_until_next_load(datetime(2026, 10, 31, 23, 58, tzinfo=oslo)) == 125
