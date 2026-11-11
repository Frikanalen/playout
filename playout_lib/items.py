"""Schedule item classes for different types of playout content."""

import asyncio
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytz
from loguru import logger

from .config import FILLER_MUSIC, FILLER_MUSIC_VOLUME


def localtime():
    """Get current time in Oslo timezone."""
    return datetime.now(tz=pytz.timezone("Europe/Oslo"))


class Item:
    """Base class for all playable items."""

    def __init__(self, layer):
        self.layer = layer
        self.prepare = None

    async def stop(self):
        """Stop playback on this item's layer."""
        from .caspar_player import current_player

        await current_player.issue(f"STOP {self.layer}")

    async def clear(self):
        """Clear this item's layer."""
        from .caspar_player import current_player

        await current_player.issue(f"CLEAR {self.layer}")

    def __repr__(self) -> str:
        return "[Item]"


class PlannedItem(Item):
    """Base class for scheduled items with start and end times."""

    def __init__(self, layer, start_time, end_time):
        self.start_time = start_time
        self.end_time = end_time
        self._end_moved = asyncio.Event()
        super().__init__(layer)

    def reschedule(self, end_time):
        """Move the end of this item, including while it is on air."""
        self.end_time = end_time
        self._end_moved.set()

    async def _wait_until_end(self, margin=0.0):
        """Block until margin seconds before the end, following any reschedule."""
        while self._seconds_left() > margin:
            self._end_moved.clear()
            sleeper = asyncio.ensure_future(asyncio.sleep(self._seconds_left() - margin))
            moved = asyncio.ensure_future(self._end_moved.wait())
            try:
                await asyncio.wait({sleeper, moved}, return_when=asyncio.FIRST_COMPLETED)
            finally:
                sleeper.cancel()
                moved.cancel()

    async def sleep_until_time_to_prepare(self):
        """Sleep until 5 seconds before scheduled start time."""
        seconds_until_start = (self.start_time - localtime()).total_seconds()
        logger.debug(f"{seconds_until_start:.2f} seconds until start.")
        await asyncio.sleep(seconds_until_start - 5)

    async def sleep_until_time_to_play(self):
        """Sleep until scheduled start time."""
        seconds_until_start = (self.start_time - localtime()).total_seconds()
        logger.debug(f"{seconds_until_start:.2f} seconds until play. {repr(self)}")
        await asyncio.sleep(seconds_until_start)

    def already_done(self):
        """Check if this item's scheduled time has passed."""
        return localtime() > self.end_time

    def _seconds_left(self):
        """Calculate remaining seconds until scheduled end."""
        return (self.end_time - localtime()).total_seconds()

    async def _completion(self):
        """Block until the scheduled end time or until cancelled."""
        logger.info(f"waiting for completion {self._seconds_left():.2f} seconds left {repr(self)}")
        await self._wait_until_end()
        logger.info(f"Finished waiting {repr(self)}")


class Graphic(PlannedItem):
    """A scheduled graphic/image overlay to be displayed."""

    def __init__(self, url, layer, start_time, end_time):
        super().__init__(layer, start_time, end_time)
        self.has_been_prepared = False
        self.music_preloaded = False
        self.url = url

    def timed_url(self):
        """The URL with its duration cut to the time left, if it started already.

        The template plans its run from that duration, counted from the cue. A
        graphic cued late, after a restart say, gets what is left of its gap.
        """
        parts = urlsplit(self.url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        if not any(key == "duration" for key, _ in query):
            return self.url
        left = min(self.end_time - self.start_time, self.end_time - localtime())
        duration_ms = max(int(left.total_seconds() * 1000), 0)
        query = [(k, str(duration_ms) if k == "duration" else v) for k, v in query]
        return urlunsplit(parts._replace(query=urlencode(query)))

    @property
    def music_layer(self):
        """The music's sub-layer, next to the template's ("1-601" for "1-60").

        Each graphic has its own, so a notice and a gap graphic back to back
        can't stop each other's music at the handover.
        """
        return f"{self.layer}2"

    async def _start_music(self, preloaded):
        """Loop the filler music, with the filler reel's own sound muted."""
        from .caspar_player import current_player

        if not FILLER_MUSIC:
            return
        await current_player.issue(f"MIXER {self.layer} VOLUME 0")
        await current_player.issue(f"MIXER {self.music_layer} VOLUME {FILLER_MUSIC_VOLUME:.4f}")
        try:
            if preloaded:
                await current_player.issue(f"PLAY {self.music_layer}")
            else:
                await current_player.issue(f"PLAY {self.music_layer} {FILLER_MUSIC} LOOP")
        except ValueError:
            # A missing file must not take the graphic off air with it.
            logger.exception(f"CasparCG can't play the filler music {FILLER_MUSIC}")

    async def cue(self):
        """Start displaying the graphic."""
        from .caspar_player import current_player

        try:
            if self.has_been_prepared:
                await current_player.issue(f"CG {self.layer}1 PLAY 0")
                await current_player.issue(f"PLAY {self.layer} filler/FrikanalenLoop loop 0")
            else:
                await current_player.issue(f'CG {self.layer}1 ADD 0 "{self.timed_url()}" 1')
                await current_player.issue(f"PLAY {self.layer}")
            await self._start_music(preloaded=self.music_preloaded)

            # If we have time for it, do a nice and steady fade to black
            # two seconds before the next programme, just like the old
            # NRK clock used to do it! ^_^ The music fades out with it.
            if self._seconds_left() >= 5.0:
                await self._wait_until_end(margin=2.0)
                await current_player.issue(f"MIXER {self.layer}1 OPACITY 0 50 easeinsine")
                await current_player.issue(f"MIXER {self.layer} OPACITY 0 50 easeinsine")
                if FILLER_MUSIC:
                    await current_player.issue(f"MIXER {self.music_layer} VOLUME 0 50 easeinsine")

            await self._completion()
            await self.clear()

        except asyncio.CancelledError:
            await self.clear()

    async def clear(self):
        """Clear the graphic and its music, and reset mixer settings."""
        from .caspar_player import current_player

        await current_player.issue(f"CLEAR {self.layer}")
        await current_player.issue(f"CG {self.layer}1 CLEAR")
        await current_player.issue(f"MIXER {self.layer}1 CLEAR")
        await current_player.issue(f"MIXER {self.layer} CLEAR")
        if FILLER_MUSIC:
            await current_player.issue(f"CLEAR {self.music_layer}")
            await current_player.issue(f"MIXER {self.music_layer} CLEAR")

    async def prepare(self):
        """Preload the graphic and its music into CasparCG."""
        from .caspar_player import current_player

        try:
            await current_player.issue(f'CG {self.layer}1 ADD 0 "{self.timed_url()}" 0')
            await current_player.issue(f"LOADBG {self.layer} filler/FrikanalenLoop loop 0")
            self.has_been_prepared = True
            if FILLER_MUSIC:
                try:
                    await current_player.issue(f"LOADBG {self.music_layer} {FILLER_MUSIC} LOOP")
                except ValueError:
                    logger.exception(f"CasparCG can't load the filler music {FILLER_MUSIC}")
                    self.music_preloaded = False
                else:
                    self.music_preloaded = True
        except asyncio.CancelledError:
            pass

    def __repr__(self):
        time_range = f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        duration = (self.end_time - self.start_time).total_seconds()
        return f"[{time_range} Graphic: {duration:.1f}s]"


class FillerLoop(PlannedItem):
    """A gap between videos too short to justify a full graphics overlay.

    Just loops the filler reel on the graphics layer instead of paying for
    a CG add/fade.
    """

    async def cue(self):
        """Loop the filler reel for the duration of the gap."""
        from .caspar_player import current_player

        try:
            await current_player.issue(f"PLAY {self.layer} filler/FrikanalenLoop loop 0")
            await self._completion()
            await self.clear()
        except asyncio.CancelledError:
            await self.clear()

    def __repr__(self):
        time_range = f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        duration = (self.end_time - self.start_time).total_seconds()
        return f"[{time_range} FillerLoop: {duration:.1f}s]"


class ProgrammeUnavailable(Graphic):
    """A notice in place of a scheduled programme whose file never arrived.

    A grant can list a video before its file is uploaded. If the file still
    isn't there at air time, viewers are told the programme isn't available
    for the length of its slot, rather than shown something else.
    """

    def __init__(self, url, layer, start_time, end_time, video_id, title):
        super().__init__(url, layer, start_time, end_time)
        self.video_id = video_id
        self.title = title

    def __repr__(self):
        time_range = f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        return f"[{time_range} Unavailable: {self.title[:15]}]"
