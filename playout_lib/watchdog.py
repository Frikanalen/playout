"""Check what CasparCG actually plays against what playout thinks it plays.

Playout only knows the commands it sent. If CasparCG loses a layer without
dropping the connection, nothing else would notice: the heartbeat still gets
its answers while the channel airs black. Once a second this reads the
channel state (AMCP INFO, the same state CasparCG sends as OSC) and compares
the programme layer with the video that should be on it.

It acts on one case only, the unambiguous one: a video that should be
playing, well inside its slot, whose layer is empty for several seconds in a
row. It recovers the same way as after a lost connection, by restarting
playout, which cues everything that should be on air at the right point. A
restart is allowed at most once per RESTART_SPACING, across restarts, so a
misreading can never put playout in a restart loop. Anything else odd (the
wrong file, a frozen clock) is logged for a person to look at, not acted on.
"""

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import PurePosixPath
from xml.etree import ElementTree

from loguru import logger

from .caspar_player import CasparConnectionLost
from .items import localtime
from .video import PrerecordedVideo

CHECK_INTERVAL = 1.0
# Leave the start of a slot alone (prepare, the MIX transition, a slow seek)
# and its end (the next item takes over the layer).
EDGE = timedelta(seconds=10)
# How long a layer must stay empty before playout acts on it.
CONFIRM_SECONDS = 5.0
# A clip that reached its end may leave the layer; that is not a failure.
END_SLACK = 2.0
# At most one restart per this many seconds, carried across the re-exec in
# the environment, so a wrong reading can't keep restarting playout.
RESTART_SPACING = 600.0
LAST_RESTART_ENV = "PLAYOUT_WATCHDOG_LAST_RESTART"


@dataclass
class Foreground:
    """What CasparCG reports for the foreground of one layer."""

    producer: str
    path: str | None = None
    time: float | None = None
    duration: float | None = None
    paused: bool = False


def read_foreground(info, layer: str) -> Foreground | None:
    """The foreground of layer ("1-50") from INFO XML, or None if it is empty.

    Raises ValueError if info is not a channel state at all, so an unreadable
    answer is never taken for an empty layer.
    """
    if not isinstance(info, str):
        raise ValueError(f"INFO returned {type(info).__name__}, not XML")
    root = ElementTree.fromstring(info.strip())
    if root.find("./stage") is None:
        raise ValueError("INFO returned no stage")
    number = layer.split("-")[1]
    foreground = root.find(f"./stage/layer/layer_{number}/foreground")
    if foreground is None:
        return None
    producer = (foreground.findtext("producer") or "").strip()
    if producer in ("", "empty"):
        return None
    times = []
    for element in foreground.findall("file/time"):
        try:
            times.append(float(element.text))
        except (TypeError, ValueError):
            pass
    paused = (foreground.findtext("paused") or "").strip().lower() == "true"
    return Foreground(
        producer=producer,
        path=foreground.findtext("file/path"),
        time=times[0] if times else None,
        duration=times[1] if len(times) > 1 else None,
        paused=paused,
    )


def same_file(planned: str, playing: str | None) -> bool:
    """Whether CasparCG's resolved path is the file playout asked for.

    CasparCG reports the full path under its media folder and may resolve
    the extension itself, so only the name without extension is compared.
    """
    if not playing:
        return False
    return PurePosixPath(planned).stem.lower() == PurePosixPath(playing).stem.lower()


class AirWatchdog:
    """Watches the programme layer while a video is on air."""

    def __init__(self, scheduler, player, clock=time.monotonic):
        self._scheduler = scheduler
        self._player = player
        self._clock = clock
        # Set when playout should restart to bring air back in line.
        self.restart = asyncio.Event()
        self._empty_since: float | None = None
        self._last_seen: Foreground | None = None
        self._watching = None
        self._warned: set[tuple] = set()
        self._blind = False

    def _video_on_air(self) -> PrerecordedVideo | None:
        now = localtime()
        for item, task in self._scheduler.tasks.values():
            if (
                isinstance(item, PrerecordedVideo)
                and item.on_air
                and not task.done()
                and item.start_time + EDGE <= now <= item.end_time - EDGE
            ):
                return item
        return None

    def _warn_once(self, key, message):
        if key not in self._warned:
            self._warned.add(key)
            logger.warning(message)

    def check(self, info):
        """Compare one INFO answer with the plan, and decide."""
        video = self._video_on_air()
        if video is not self._watching:
            self._watching = video
            self._empty_since = None
            self._last_seen = None
        if video is None:
            return

        foreground = read_foreground(info, video.layer)
        now = self._clock()

        if foreground is None:
            seen = self._last_seen
            if seen and seen.time is not None and seen.duration:
                if seen.time >= seen.duration - END_SLACK:
                    return  # The clip ran to its end.
            if self._empty_since is None:
                self._empty_since = now
                logger.warning(f"Layer {video.layer} is empty while {video!r} should be playing")
            if now - self._empty_since >= CONFIRM_SECONDS:
                self._recover(f"layer {video.layer} has been empty while {video!r} should play")
            return

        self._empty_since = None
        if foreground.producer == "ffmpeg":
            if not same_file(video.filename, foreground.path):
                self._warn_once(
                    ("file", id(video)),
                    f"Layer {video.layer} plays {foreground.path} while {video!r} "
                    f"should be playing {video.filename}",
                )
            previous = self._last_seen
            if (
                previous is not None
                and previous.time is not None
                and foreground.time == previous.time
                and not foreground.paused
                and foreground.duration
                and foreground.time < foreground.duration - END_SLACK
            ):
                self._warn_once(
                    ("frozen", id(video), foreground.time),
                    f"Layer {video.layer} is stuck at {foreground.time:.2f} s in {foreground.path}",
                )
            self._last_seen = foreground

    def _recover(self, reason):
        if self.restart.is_set():
            return
        last = float(os.environ.get(LAST_RESTART_ENV, "0") or 0)
        wall = time.time()
        if wall - last < RESTART_SPACING:
            self._warn_once(
                ("spacing", self._watching and id(self._watching)),
                f"Air doesn't match the plan ({reason}), but playout restarted for that "
                f"{wall - last:.0f} s ago; not restarting again so soon",
            )
            return
        logger.error(f"Air doesn't match the plan: {reason}; restarting playout")
        os.environ[LAST_RESTART_ENV] = str(wall)
        self.restart.set()

    async def run(self):
        """Check once a second until the connection goes or a restart is due."""
        while not self.restart.is_set():
            await asyncio.sleep(CHECK_INTERVAL)
            try:
                info = await self._player.issue("INFO 1", quiet=True)
                self.check(info)
                if self._blind:
                    logger.info("The air watchdog can read the channel state again")
                    self._blind = False
            except CasparConnectionLost:
                return
            except Exception as error:
                # Never act on what can't be read; just say so, once.
                if not self._blind:
                    logger.warning(f"The air watchdog can't read the channel state ({error!r})")
                    self._blind = True
