"""Schedule management and item playback coordination.

The scheduler keeps one task per schedule item and reconciles that set
against the schedule whenever Django says it changed, and every
POLL_INTERVAL in case a notice went missing. Reconciling changes only what
differs: an item that is still booked as it was keeps its task, one that
moved or went away is cancelled, and a new one gets a task of its own.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta

from loguru import logger

from .api import load_schedule
from .config import API_URL
from .events import listen_for_changes
from .items import PlannedItem, localtime

# The fallback for a missed or broken event stream.
POLL_INTERVAL = timedelta(seconds=60)
# A booking often lands as a couple of commits in quick succession (the
# schedule item, then its live transmission): wait for the rest of them.
SETTLE_SECONDS = 0.5


def item_key(item: PlannedItem) -> tuple:
    """What makes two loads' items the same item, apart from where it ends.

    Graphics are told their duration in their URL, so the URL is left out:
    a gap that shrinks keeps its graphic on air and just ends it sooner.
    """
    identity = getattr(item, "video_id", None) or getattr(item, "stream_id", None)
    return (type(item).__name__, item.layer, item.start_time, identity)


def _log_failure(item, task: asyncio.Task):
    if not task.cancelled() and task.exception() is not None:
        logger.opt(exception=task.exception()).error(f"{item!r} failed")


class Scheduler:
    """Plays the schedule, keeping its tasks in step with Django's."""

    def __init__(
        self,
        load: Callable[[], Awaitable[list[PlannedItem]]] = lambda: load_schedule(API_URL),
        listen: Callable[[Callable[[], None]], Awaitable[None]] = lambda changed: (
            listen_for_changes(API_URL, changed)
        ),
    ):
        self._load = load
        self._listen = listen
        self._changed = asyncio.Event()
        # Item key -> (the item, the task playing it).
        self.tasks: dict[tuple, tuple[PlannedItem, asyncio.Task]] = {}

    async def _play_item(self, item):
        """Prepare item ahead if it can be, then cue it at its start time."""
        prepare_op = getattr(item, "prepare", None)
        if callable(prepare_op):
            await item.sleep_until_time_to_prepare()
            logger.info(f"Preparing {item!r}")
            await prepare_op()
            # Most prepare() methods swallow a cancellation; don't cue an
            # item that was taken off the schedule while it prepared.
            if asyncio.current_task().cancelling():
                raise asyncio.CancelledError

        await item.sleep_until_time_to_play()
        logger.info(f"Playing item {item!r}")
        await item.cue()

    async def _cancel(self, item, task):
        logger.info(f"Taking {item!r} off the schedule")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception(f"{item!r} failed while being cancelled")
        # Cancelled before it was cued: undo anything prepare() left behind.
        abort = getattr(item, "abort", None)
        if callable(abort):
            await abort()

    def _start(self, item):
        logger.info(f"Adding cue to task list: {item!r}")
        task = asyncio.create_task(self._play_item(item))
        task.add_done_callback(lambda task: _log_failure(item, task))
        self.tasks[item_key(item)] = (item, task)

    async def reconcile(self, schedule: list[PlannedItem]):
        """Bring the running tasks in line with schedule."""
        now = localtime()
        wanted = {item_key(item): item for item in schedule if not item.already_done()}

        # A task that ended early (one that failed, say) stays on the books
        # until its slot is over, rather than being restarted on every load.
        for key, (item, task) in list(self.tasks.items()):
            if task.done() and item.already_done():
                del self.tasks[key]

        # Cancel first, so the layers are clear before any replacement starts.
        for key, (item, task) in list(self.tasks.items()):
            booked = wanted.get(key)
            if booked is None:
                await self._cancel(item, task)
                del self.tasks[key]
            elif booked.end_time != item.end_time:
                if item.start_time <= now:
                    # On air: keep it going and only move where it stops.
                    logger.info(f"{item!r} now ends at {booked.end_time:%H:%M:%S}")
                    item.reschedule(booked.end_time)
                else:
                    await self._cancel(item, task)
                    del self.tasks[key]

        for key, item in sorted(wanted.items(), key=lambda kv: kv[1].start_time):
            if key not in self.tasks:
                self._start(item)

    def changed(self):
        """Ask for the schedule to be fetched again now."""
        self._changed.set()

    async def run(self):
        """Main scheduler loop: reload and reconcile on every change."""
        listener = asyncio.create_task(self._listen(self.changed))
        self.changed()
        try:
            while True:
                try:
                    await asyncio.wait_for(self._changed.wait(), POLL_INTERVAL.total_seconds())
                    await asyncio.sleep(SETTLE_SECONDS)
                except TimeoutError:
                    pass
                self._changed.clear()
                try:
                    schedule = await self._load()
                except Exception:
                    # Keep playing what is queued; the next change or poll retries.
                    logger.exception("Failed to load the schedule, keeping the current one")
                    continue
                await self.reconcile(schedule)
        finally:
            listener.cancel()
